from __future__ import annotations

import argparse
import os
import tempfile
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from pdf_ocr.model_lock import (
    MODEL_LOCK_SCHEMA,
    MODEL_LOCK_FORMAT_CHECKER,
    REQUIRED_ROLES,
    ModelLockError,
    _descendants,
    _resolve_inside_model_home,
    _validate_component_role,
    _validate_entrypoint,
    sha256,
)
from pdf_ocr.runtime import locked_runtime_versions
from pdf_ocr.strict_json import StrictJsonError, strict_json_loads


SOURCE_RECEIPT_SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "source-receipt.schema.json"
)
DEFAULT_UV_LOCK = Path(__file__).resolve().parents[1] / "uv.lock"


def _validated_receipt(receipt_path: Path) -> dict[str, object]:
    try:
        payload = strict_json_loads(
            receipt_path.read_bytes(),
            description="source receipt",
        )
    except StrictJsonError as error:
        raise ModelLockError(str(error)) from error
    schema = strict_json_loads(
        SOURCE_RECEIPT_SCHEMA.read_bytes(),
        description="source receipt schema",
    )
    Draft202012Validator(
        schema,
        format_checker=MODEL_LOCK_FORMAT_CHECKER,
    ).validate(payload)
    return payload


def build_lock(
    model_home: Path,
    receipt_path: Path,
    uv_lock_path: Path = DEFAULT_UV_LOCK,
) -> dict[str, object]:
    receipt = _validated_receipt(receipt_path)
    artifacts = receipt["artifacts"]
    roles = [item["role"] for item in artifacts]
    if len(roles) != len(set(roles)):
        duplicate = next(role for role in roles if roles.count(role) > 1)
        raise ModelLockError(f"duplicate model role: {duplicate}")
    missing = REQUIRED_ROLES - set(roles)
    if missing:
        raise ModelLockError(
            f"source receipt is missing roles: {', '.join(sorted(missing))}"
        )

    locked_artifacts: list[dict[str, object]] = []
    for item in artifacts:
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
        files = sorted(
            (path for path in descendants if path.is_file()),
            key=lambda path: path.relative_to(artifact_root).as_posix(),
        )
        if not files:
            raise ModelLockError(f"model artifact is empty: {role}")
        actual_paths = {
            path.relative_to(artifact_root).as_posix(): path
            for path in files
        }
        _validate_entrypoint(entrypoint, artifact_root, actual_paths, role)
        empty_directories = [
            path for path in descendants
            if path.is_dir() and not any(path.iterdir())
        ]
        if empty_directories:
            raise ModelLockError(
                f"model artifact contains empty directory: {empty_directories[0]}"
            )

        file_records: list[dict[str, object]] = []
        for path in files:
            byte_count = path.stat().st_size
            if byte_count == 0:
                raise ModelLockError(f"model artifact contains zero-byte file: {path}")
            file_records.append(
                {
                    "path": path.relative_to(artifact_root).as_posix(),
                    "bytes": byte_count,
                    "sha256": f"sha256:{sha256(path)}",
                }
            )
        locked_artifacts.append({**item, "files": file_records})

    versions = locked_runtime_versions(uv_lock_path)
    payload: dict[str, object] = {
        "schema_version": "2.0.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cache_environment_variable": "PDF_OCR_MODEL_HOME",
        "packages": [
            {"name": name, "version": version}
            for name, version in versions.items()
        ],
        "artifacts": locked_artifacts,
    }
    schema = strict_json_loads(
        MODEL_LOCK_SCHEMA.read_bytes(),
        description="model lock schema",
    )
    Draft202012Validator(
        schema,
        format_checker=MODEL_LOCK_FORMAT_CHECKER,
    ).validate(payload)
    return payload


def write_lock(output_path: Path, payload: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    ) as output_file:
        import json

        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
        temporary_path = Path(output_file.name)
    os.replace(temporary_path, output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an offline PDF OCR model lock from a source receipt."
    )
    parser.add_argument(
        "--model-home",
        type=Path,
        default=os.environ.get("PDF_OCR_MODEL_HOME"),
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--uv-lock", type=Path, default=DEFAULT_UV_LOCK)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.model_home is None:
        parser.error(
            "--model-home or the PDF_OCR_MODEL_HOME environment variable is required"
        )

    payload = build_lock(
        args.model_home.resolve(),
        args.receipt.resolve(),
        args.uv_lock.resolve(),
    )
    write_lock(args.output.resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
