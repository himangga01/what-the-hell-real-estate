from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import stat
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from .strict_json import StrictJsonError, strict_json_loads


MODEL_LOCK_SCHEMA = (
    Path(__file__).resolve().parents[2] / "schemas" / "model-lock.schema.json"
)
REQUIRED_ROLES = {
    "rapidocr_det",
    "rapidocr_cls",
    "rapidocr_rec",
    "rapidocr_rec_keys",
    "rapidocr_font",
    "docling_layout",
    "tableformer",
}
ROLE_COMPONENTS = {
    "rapidocr_det": "RAPIDOCR",
    "rapidocr_cls": "RAPIDOCR",
    "rapidocr_rec": "RAPIDOCR",
    "rapidocr_rec_keys": "RAPIDOCR",
    "rapidocr_font": "RAPIDOCR",
    "docling_layout": "DOCLING",
    "tableformer": "TABLEFORMER",
}
_RFC3986_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-._~"
)
_RFC3986_SUBDELIMITERS = frozenset("!$&'()*+,;=")
_RFC3986_PATH_CHARACTERS = (
    _RFC3986_UNRESERVED | _RFC3986_SUBDELIMITERS | frozenset(":@/")
)
_RFC3986_QUERY_CHARACTERS = _RFC3986_PATH_CHARACTERS | frozenset("?")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)


def _valid_percent_encoded_component(
    value: str,
    allowed_characters: frozenset[str],
) -> bool:
    index = 0
    while index < len(value):
        character = value[index]
        if character == "%":
            if (
                index + 2 >= len(value)
                or not all(
                    item in "0123456789ABCDEFabcdef"
                    for item in value[index + 1:index + 3]
                )
            ):
                return False
            index += 3
            continue
        if character not in allowed_characters:
            return False
        index += 1
    return True


def _valid_uri(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in value)
        or _INVALID_PERCENT_ESCAPE.search(value)
    ):
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or "@" in parsed.netloc
        or "#" in value
        or re.fullmatch(
            r"[A-Za-z0-9.-]+(?::[0-9]+)?",
            parsed.netloc,
        ) is None
        or not _valid_percent_encoded_component(
            parsed.path,
            _RFC3986_PATH_CHARACTERS,
        )
        or not _valid_percent_encoded_component(
            parsed.query,
            _RFC3986_QUERY_CHARACTERS,
        )
    ):
        return False
    if ":" in parsed.netloc and (
        port is None or not 1 <= port <= 65535
    ):
        return False
    try:
        return isinstance(ipaddress.ip_address(hostname), ipaddress.IPv4Address)
    except ValueError:
        pass
    if hostname.replace(".", "").isdigit():
        return False
    labels = hostname.split(".")
    return (
        len(hostname) <= 253
        and all(
            label
            and len(label) <= 63
            and label[0] != "-"
            and label[-1] != "-"
            and all(character.isalnum() or character == "-" for character in label)
            for label in labels
        )
    )


def _valid_datetime(value: object) -> bool:
    if not isinstance(value, str) or _RFC3339_DATETIME.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


MODEL_LOCK_FORMAT_CHECKER = FormatChecker()
MODEL_LOCK_FORMAT_CHECKER.checkers["uri"] = (_valid_uri, ())
MODEL_LOCK_FORMAT_CHECKER.checkers["date-time"] = (_valid_datetime, ())


class ModelLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class LockedFile:
    path: Path
    bytes: int
    sha256: str
    relative_path: PurePosixPath


@dataclass(frozen=True)
class LockedArtifact:
    component: str
    role: str
    name: str
    source_url: str
    license: str
    model_home: Path
    root_relative_path: PurePosixPath
    entrypoint_relative_path: PurePosixPath
    root: Path
    path: Path
    files: tuple[LockedFile, ...]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_from_posix(value: str) -> Path:
    return Path(*PurePosixPath(value).parts)


def _relative_posix_path(
    value: object,
    *,
    description: str,
    allow_current_directory: bool = False,
) -> PurePosixPath:
    if isinstance(value, PurePosixPath):
        text = value.as_posix()
    elif isinstance(value, str):
        text = value
    else:
        raise ModelLockError(f"{description} must be a relative POSIX path")
    if allow_current_directory and text == ".":
        return PurePosixPath(".")
    segments = text.split("/")
    if (
        not text
        or text.startswith("/")
        or "\\" in text
        or "\x00" in text
        or ":" in text
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise ModelLockError(f"{description} must be a safe relative POSIX path")
    normalized = PurePosixPath(text)
    if normalized.is_absolute() or normalized.as_posix() != text:
        raise ModelLockError(f"{description} must be a safe relative POSIX path")
    return normalized


def _is_link_like(path: Path) -> bool:
    if path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    ):
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(
        attributes
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _require_inside(parent: Path, child: Path, description: str) -> None:
    try:
        child.relative_to(parent)
    except ValueError as error:
        raise ModelLockError(f"{description} escapes model home") from error


def _reject_link_components(
    base: Path,
    relative: Path,
    description: str,
) -> None:
    candidate = base
    for part in relative.parts:
        candidate /= part
        if _is_link_like(candidate):
            raise ModelLockError(f"{description} must not contain a symlink")


def _reject_existing_absolute_ancestor_links(
    path: Path,
    description: str,
) -> None:
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    if not parts:
        raise ModelLockError(f"{description} must be absolute")
    candidate = Path(parts[0])
    if candidate.exists() and _is_link_like(candidate):
        raise ModelLockError(
            f"{description} absolute ancestor is a link or reparse point"
        )
    for part in parts[1:]:
        candidate /= part
        if not candidate.exists():
            break
        if _is_link_like(candidate):
            raise ModelLockError(
                f"{description} absolute ancestor is a link or reparse point"
            )


def _resolve_inside_model_home(
    model_home: Path,
    root_value: str,
    entrypoint_value: str,
) -> tuple[Path, Path]:
    root_relative = _relative_posix_path(
        root_value,
        description="model artifact root",
    )
    entrypoint_relative = _relative_posix_path(
        entrypoint_value,
        description="model entrypoint",
        allow_current_directory=True,
    )
    raw_root = _path_from_posix(root_relative.as_posix())
    raw_entrypoint = _path_from_posix(entrypoint_relative.as_posix())
    if raw_root.is_absolute() or raw_entrypoint.is_absolute():
        raise ModelLockError("model path must be relative to model home")

    lexical_home = Path(os.path.abspath(model_home))
    _reject_existing_absolute_ancestor_links(lexical_home, "model home")
    if _is_link_like(lexical_home):
        raise ModelLockError("model home must not be a link or reparse point")
    root = lexical_home.resolve()
    _reject_link_components(root, raw_root, "model artifact root")
    artifact_candidate = root / raw_root
    artifact_root = artifact_candidate.resolve()
    _require_inside(root, artifact_root, "model artifact root")

    _reject_link_components(artifact_root, raw_entrypoint, "model entrypoint")
    entrypoint_candidate = artifact_root / raw_entrypoint
    entrypoint = entrypoint_candidate.resolve()
    _require_inside(artifact_root, entrypoint, "model entrypoint")
    return artifact_root, entrypoint


def _descendants(artifact_root: Path, role: str) -> list[Path]:
    descendants = list(artifact_root.rglob("*"))
    if any(_is_link_like(path) for path in descendants):
        raise ModelLockError(f"model artifact contains symlink: {role}")
    if any(not path.is_file() and not path.is_dir() for path in descendants):
        raise ModelLockError(f"model artifact contains a non-regular path: {role}")
    if any(
        path.is_file() and getattr(path.stat(), "st_nlink", 1) != 1
        for path in descendants
    ):
        raise ModelLockError(f"model artifact contains hardlink: {role}")
    return descendants


def _validate_component_role(component: str, role: str) -> None:
    if ROLE_COMPONENTS.get(role) != component:
        raise ModelLockError(
            f"model component/role combination is invalid: {component}/{role}"
        )


def _validate_entrypoint(
    entrypoint: Path,
    artifact_root: Path,
    actual_paths: Mapping[str, Path],
    role: str,
) -> None:
    if not entrypoint.exists():
        raise ModelLockError(f"model entrypoint is missing: {role}")
    if entrypoint.is_file():
        relative = entrypoint.relative_to(artifact_root).as_posix()
        if relative not in actual_paths:
            raise ModelLockError(f"model entrypoint is not locked: {role}")
        return
    if not entrypoint.is_dir():
        raise ModelLockError(f"model entrypoint is not a file or directory: {role}")
    if not any(
        path == entrypoint or entrypoint in path.parents
        for path in actual_paths.values()
    ):
        raise ModelLockError(f"model entrypoint directory is empty: {role}")


def load_model_lock(
    lock_path: Path,
    model_home: Path,
    runtime_versions: Mapping[str, str],
) -> tuple[LockedArtifact, ...]:
    try:
        payload = strict_json_loads(
            lock_path.read_bytes(),
            description="model lock",
        )
    except StrictJsonError as error:
        raise ModelLockError(str(error)) from error
    schema = strict_json_loads(
        MODEL_LOCK_SCHEMA.read_bytes(),
        description="model lock schema",
    )
    Draft202012Validator(
        schema,
        format_checker=MODEL_LOCK_FORMAT_CHECKER,
    ).validate(payload)

    package_items = payload["packages"]
    package_names = [item["name"] for item in package_items]
    if len(package_names) != len(set(package_names)):
        raise ModelLockError("model lock contains duplicate package names")
    locked_versions = {
        item["name"]: item["version"]
        for item in package_items
    }
    if locked_versions != dict(runtime_versions):
        raise ModelLockError("model lock package versions do not match runtime")

    role_items = [item["role"] for item in payload["artifacts"]]
    if len(role_items) != len(set(role_items)):
        duplicate = next(
            role for role in role_items if role_items.count(role) > 1
        )
        raise ModelLockError(f"duplicate model role: {duplicate}")
    missing = REQUIRED_ROLES - set(role_items)
    if missing:
        raise ModelLockError(
            f"model lock is missing roles: {', '.join(sorted(missing))}"
        )

    artifacts: list[LockedArtifact] = []
    for item in payload["artifacts"]:
        role = item["role"]
        _validate_component_role(item["component"], role)
        artifact_root, entrypoint = _resolve_inside_model_home(
            model_home,
            item["root"],
            item["entrypoint"],
        )
        if not artifact_root.is_dir():
            raise ModelLockError(f"model artifact is missing: {role}")

        descendants = _descendants(artifact_root, role)
        actual_paths = {
            path.relative_to(artifact_root).as_posix(): path
            for path in descendants
            if path.is_file()
        }
        records = item["files"]
        record_paths = [record["path"] for record in records]
        if len(record_paths) != len(set(record_paths)):
            raise ModelLockError(f"duplicate model file path: {role}")
        expected_files = {record["path"]: record for record in records}
        locked_paths = {
            relative_path: actual_paths[relative_path]
            for relative_path in expected_files
            if relative_path in actual_paths
        }
        _validate_entrypoint(entrypoint, artifact_root, locked_paths, role)
        if set(actual_paths) != set(expected_files):
            raise ModelLockError(f"model file list does not match lock: {role}")

        locked_files: list[LockedFile] = []
        for relative_path, record in expected_files.items():
            path = actual_paths[relative_path]
            if path.stat().st_size != record["bytes"]:
                raise ModelLockError(f"model file size mismatch: {path}")
            if f"sha256:{sha256(path)}" != record["sha256"]:
                raise ModelLockError(f"model file SHA-256 mismatch: {path}")
            locked_files.append(
                LockedFile(
                    path=path,
                    bytes=record["bytes"],
                    sha256=record["sha256"],
                    relative_path=PurePosixPath(relative_path),
                )
            )
        artifacts.append(
            LockedArtifact(
                component=item["component"],
                role=role,
                name=item["name"],
                source_url=item["source_url"],
                license=item["license"],
                model_home=Path(os.path.abspath(model_home)),
                root_relative_path=PurePosixPath(item["root"]),
                entrypoint_relative_path=PurePosixPath(item["entrypoint"]),
                root=artifact_root,
                path=entrypoint,
                files=tuple(locked_files),
            )
        )
    result = tuple(artifacts)
    revalidate_locked_artifacts(result)
    return result


def revalidate_locked_artifacts(
    artifacts: Sequence[LockedArtifact],
) -> None:
    if not artifacts:
        raise ModelLockError("locked artifacts must not be empty")
    roles = [artifact.role for artifact in artifacts]
    if len(roles) != len(set(roles)):
        raise ModelLockError("locked artifacts contain duplicate model roles")
    for artifact in artifacts:
        _validate_component_role(artifact.component, artifact.role)
        if not artifact.files:
            raise ModelLockError(
                f"locked artifact files must not be empty: {artifact.role}"
            )

        model_home = Path(os.path.abspath(artifact.model_home))
        root_relative = _relative_posix_path(
            artifact.root_relative_path,
            description="locked artifact root",
        )
        entrypoint_relative = _relative_posix_path(
            artifact.entrypoint_relative_path,
            description="locked artifact entrypoint",
            allow_current_directory=True,
        )
        expected_root, expected_entrypoint = _resolve_inside_model_home(
            model_home,
            root_relative.as_posix(),
            entrypoint_relative.as_posix(),
        )
        if model_home != artifact.model_home:
            raise ModelLockError("locked artifact model_home binding is invalid")
        if expected_root != artifact.root:
            raise ModelLockError("locked artifact root binding is invalid")
        if expected_entrypoint != artifact.path:
            raise ModelLockError("locked artifact entrypoint binding is invalid")
        if not artifact.root.is_dir():
            raise ModelLockError(
                f"locked artifact root is missing: {artifact.role}"
            )

        descendants = _descendants(artifact.root, artifact.role)
        actual_files = {
            path.relative_to(artifact.root).as_posix(): path
            for path in descendants
            if path.is_file()
        }
        actual_directories = {
            path.relative_to(artifact.root).as_posix()
            for path in descendants
            if path.is_dir()
        }
        locked_relative_paths: list[str] = []
        implied_directories: set[str] = set()
        for locked_file in artifact.files:
            relative_path = _relative_posix_path(
                locked_file.relative_path,
                description="locked model file",
            )
            relative_text = relative_path.as_posix()
            if relative_text in locked_relative_paths:
                raise ModelLockError(
                    f"duplicate locked model file: {artifact.role}/{relative_text}"
                )
            locked_relative_paths.append(relative_text)
            parent = relative_path.parent
            while parent != PurePosixPath("."):
                implied_directories.add(parent.as_posix())
                parent = parent.parent
            expected_path = artifact.root / _path_from_posix(relative_text)
            if Path(os.path.abspath(locked_file.path)) != expected_path:
                raise ModelLockError(
                    f"locked model file path binding is invalid: {locked_file.path}"
                )
            path = locked_file.path
            if (
                isinstance(locked_file.bytes, bool)
                or not isinstance(locked_file.bytes, int)
                or locked_file.bytes < 1
                or not isinstance(locked_file.sha256, str)
                or re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    locked_file.sha256,
                )
                is None
            ):
                raise ModelLockError(
                    f"locked model file metadata is invalid: {path}"
                )
            relative_native = path.relative_to(artifact.root)
            _reject_link_components(
                artifact.root,
                relative_native,
                "locked model file",
            )
            if _is_link_like(path) or not path.is_file():
                raise ModelLockError(
                    f"model file is missing or linked: {path}"
                )
            if getattr(path.stat(), "st_nlink", 1) != 1:
                raise ModelLockError(f"model file is a hardlink: {path}")
            if path.stat().st_size != locked_file.bytes:
                raise ModelLockError(f"model file size mismatch: {path}")
            if f"sha256:{sha256(path)}" != locked_file.sha256:
                raise ModelLockError(f"model file SHA-256 mismatch: {path}")
        if set(locked_relative_paths) != set(actual_files):
            raise ModelLockError(
                f"model file list does not match descendants: {artifact.role}"
            )
        if actual_directories != implied_directories:
            raise ModelLockError(
                f"model directory list does not match descendants: {artifact.role}"
            )
        locked_paths = {
            relative: actual_files[relative]
            for relative in locked_relative_paths
        }
        _validate_entrypoint(
            artifact.path,
            artifact.root,
            locked_paths,
            artifact.role,
        )


def optional_artifact_path(
    artifacts: Sequence[LockedArtifact],
    role: str,
) -> Path | None:
    matches = [artifact.path for artifact in artifacts if artifact.role == role]
    if len(matches) > 1:
        raise ModelLockError(f"duplicate model role: {role}")
    return matches[0] if matches else None


def artifact_path(
    artifacts: Sequence[LockedArtifact],
    role: str,
) -> Path:
    value = optional_artifact_path(artifacts, role)
    if value is None:
        raise ModelLockError(f"missing model role: {role}")
    return value


def docling_artifacts_root(
    artifacts: Sequence[LockedArtifact],
) -> Path:
    paths = [
        artifact.path
        for artifact in artifacts
        if artifact.role in {"docling_layout", "tableformer"}
    ]
    if len(paths) != 2:
        raise ModelLockError("Docling layout and TableFormer roots are required")
    roots = [path if path.is_dir() else path.parent for path in paths]
    try:
        common = Path(os.path.commonpath([str(path) for path in roots]))
    except ValueError as error:
        raise ModelLockError(
            "Docling artifacts do not have a common root"
        ) from error
    if not common.is_dir():
        raise ModelLockError("Docling artifacts root is missing")
    return common
