from pathlib import Path

import pytest

import pdf_ocr.runtime as runtime
from pdf_ocr.runtime import (
    RuntimeContractError,
    collect_runtime_info,
    locked_runtime_versions,
    require_cpu_execution_provider,
)


LOCK_PATH = Path(__file__).parents[1] / "uv.lock"


def test_missing_cpu_execution_provider_is_rejected() -> None:
    with pytest.raises(RuntimeContractError, match="CPUExecutionProvider"):
        require_cpu_execution_provider(["CUDAExecutionProvider"])


def test_cpu_execution_provider_is_selected_explicitly() -> None:
    assert require_cpu_execution_provider(
        ["AzureExecutionProvider", "CPUExecutionProvider"]
    ) == "CPUExecutionProvider"


def test_lock_contains_each_required_runtime_distribution() -> None:
    assert locked_runtime_versions(LOCK_PATH).keys() == {
        "rapidocr",
        "onnxruntime",
        "docling",
        "docling-ibm-models",
    }


def test_installed_runtime_version_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    locked = locked_runtime_versions(LOCK_PATH)

    def installed_version(name: str) -> str:
        if name == "rapidocr":
            return "0.0.0"
        return locked[name]

    monkeypatch.setattr(runtime.importlib.metadata, "version", installed_version)

    with pytest.raises(RuntimeContractError, match="do not match uv.lock"):
        collect_runtime_info(LOCK_PATH)
