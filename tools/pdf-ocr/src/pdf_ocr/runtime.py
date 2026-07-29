from __future__ import annotations

import importlib.metadata
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

LOCKED_DISTRIBUTIONS = (
    "rapidocr",
    "onnxruntime",
    "docling",
    "docling-ibm-models",
)


class RuntimeContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeInfo:
    package_versions: dict[str, str]
    execution_provider: str


def locked_runtime_versions(lock_path: Path) -> dict[str, str]:
    payload = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions = {
        str(item["name"]): str(item["version"])
        for item in payload.get("package", [])
    }
    missing = [name for name in LOCKED_DISTRIBUTIONS if name not in versions]
    if missing:
        raise RuntimeContractError(
            f"uv.lock is missing runtime packages: {', '.join(missing)}"
        )
    return {name: versions[name] for name in LOCKED_DISTRIBUTIONS}


def require_cpu_execution_provider(providers: Sequence[str]) -> str:
    if "CPUExecutionProvider" not in providers:
        raise RuntimeContractError("ONNX CPUExecutionProvider is unavailable")
    return "CPUExecutionProvider"


def collect_runtime_info(lock_path: Path) -> RuntimeInfo:
    import onnxruntime

    locked = locked_runtime_versions(lock_path)
    installed = {
        name: importlib.metadata.version(name) for name in LOCKED_DISTRIBUTIONS
    }
    mismatches = {
        name: (locked[name], installed[name])
        for name in LOCKED_DISTRIBUTIONS
        if locked[name] != installed[name]
    }
    if mismatches:
        raise RuntimeContractError(
            f"installed packages do not match uv.lock: {mismatches}"
        )
    provider = require_cpu_execution_provider(onnxruntime.get_available_providers())
    return RuntimeInfo(
        package_versions=installed,
        execution_provider=provider,
    )
