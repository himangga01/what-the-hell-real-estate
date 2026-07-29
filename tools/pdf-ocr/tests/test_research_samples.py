from __future__ import annotations

import json
import os
import re
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from pdf_ocr import cli as cli_module
from pdf_ocr import pipeline as pipeline_module
from pdf_ocr.pipeline import PdfOcrError, STAGING_OWNER_MARKER


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WRAPPER_PATH = REPOSITORY_ROOT / "scripts" / "research" / "extract-pdf.ps1"


def cli_arguments(tmp_path: Path) -> tuple[list[str], dict[str, Path]]:
    input_path = tmp_path / "notice.pdf"
    input_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    model_lock_path = tmp_path / "models.lock.json"
    model_lock_path.write_text("{}", encoding="utf-8")
    model_home = tmp_path / "models"
    model_home.mkdir()
    uv_lock_path = tmp_path / "uv.lock"
    uv_lock_path.write_text("version = 1\n", encoding="utf-8")
    output_dir = tmp_path / "result"
    paths = {
        "input": input_path.resolve(),
        "output": output_dir.resolve(),
        "model_lock": model_lock_path.resolve(),
        "model_home": model_home.resolve(),
        "uv_lock": uv_lock_path.resolve(),
    }
    arguments = [
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
        "--model-lock",
        str(model_lock_path),
        "--model-home",
        str(model_home),
        "--uv-lock",
        str(uv_lock_path),
    ]
    return arguments, paths


def fake_uv_environment(
    tmp_path: Path,
    *,
    exit_code: int,
    create_stage: bool = False,
    omit_owner_marker: bool = False,
    marker_value: str | None = None,
    other_stage: Path | None = None,
    link_target: Path | None = None,
) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    log_path = tmp_path / f"uv-{exit_code}-{len(list(tmp_path.glob('uv-*.log')))}.log"
    fake_uv = fake_bin / "uv.cmd"
    fake_uv.write_text(
        "@echo off\r\n"
        'echo ARGS=%*>"%PDF_OCR_TEST_LOG%"\r\n'
        '>>"%PDF_OCR_TEST_LOG%" echo HF_HUB_OFFLINE=%HF_HUB_OFFLINE%\r\n'
        '>>"%PDF_OCR_TEST_LOG%" echo TRANSFORMERS_OFFLINE=%TRANSFORMERS_OFFLINE%\r\n'
        '>>"%PDF_OCR_TEST_LOG%" echo UV_OFFLINE=%UV_OFFLINE%\r\n'
        'echo PDF_OCR_MODEL_HOME=%PDF_OCR_MODEL_HOME%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'echo DOCLING_ARTIFACTS_PATH=%DOCLING_ARTIFACTS_PATH%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'echo RECOVERY_TOKEN=%PDF_OCR_RECOVERY_TOKEN%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'echo STAGING_NONCE=%PDF_OCR_STAGING_NONCE%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'echo STAGING_PATH=%PDF_OCR_STAGING_PATH%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'echo RECOVERY_RECEIPT=%PDF_OCR_RECOVERY_RECEIPT%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'set /p RECEIPT_VALUE=<"%PDF_OCR_RECOVERY_RECEIPT%"\r\n'
        'call echo RECEIPT_VALUE=%%RECEIPT_VALUE%%>>"%PDF_OCR_TEST_LOG%"\r\n'
        'if not "%PDF_OCR_FAKE_CREATE_STAGE%"=="1" goto other_stage\r\n'
        'mkdir "%PDF_OCR_STAGING_PATH%" >NUL 2>NUL\r\n'
        'if "%PDF_OCR_FAKE_OMIT_MARKER%"=="1" goto stage_link\r\n'
        'if defined PDF_OCR_FAKE_MARKER_VALUE goto foreign_marker\r\n'
        '<NUL set /p "=%PDF_OCR_RECOVERY_TOKEN%">"%PDF_OCR_STAGING_PATH%\\'
        f'{STAGING_OWNER_MARKER}"\r\n'
        "goto stage_link\r\n"
        ":foreign_marker\r\n"
        '<NUL set /p "=%PDF_OCR_FAKE_MARKER_VALUE%">"%PDF_OCR_STAGING_PATH%\\'
        f'{STAGING_OWNER_MARKER}"\r\n'
        ":stage_link\r\n"
        'if not defined PDF_OCR_FAKE_LINK_TARGET goto other_stage\r\n'
        'mklink /J "%PDF_OCR_STAGING_PATH%\\linked" '
        '"%PDF_OCR_FAKE_LINK_TARGET%" >NUL\r\n'
        ":other_stage\r\n"
        'if not defined PDF_OCR_FAKE_OTHER_STAGE goto response\r\n'
        'mkdir "%PDF_OCR_FAKE_OTHER_STAGE%" >NUL 2>NUL\r\n'
        '<NUL set /p "=pdf-ocr-owned-staging-v1">'
        '"%PDF_OCR_FAKE_OTHER_STAGE%\\.pdf-ocr-staging-owner"\r\n'
        ":response\r\n"
        'echo {"status":"SUCCEEDED","manifest":"fake-manifest.json"}\r\n'
        "exit /b %PDF_OCR_FAKE_EXIT%\r\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "PDF_OCR_TEST_LOG": str(log_path),
        "PDF_OCR_FAKE_EXIT": str(exit_code),
    }
    if create_stage:
        environment["PDF_OCR_FAKE_CREATE_STAGE"] = "1"
    if omit_owner_marker:
        environment["PDF_OCR_FAKE_OMIT_MARKER"] = "1"
    if marker_value is not None:
        environment["PDF_OCR_FAKE_MARKER_VALUE"] = marker_value
    if other_stage is not None:
        environment["PDF_OCR_FAKE_OTHER_STAGE"] = str(other_stage)
    if link_target is not None:
        environment["PDF_OCR_FAKE_LINK_TARGET"] = str(link_target)
    return environment, log_path


def run_wrapper(
    input_path: Path,
    output_dir: Path,
    model_lock_path: Path,
    model_home: Path,
    *,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WRAPPER_PATH),
            "-InputPath",
            str(input_path),
            "-OutputDirectory",
            str(output_dir),
            "-ModelLockPath",
            str(model_lock_path),
            "-ModelHome",
            str(model_home),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=environment,
    )


def wrapper_paths(tmp_path: Path) -> dict[str, Path]:
    input_path = tmp_path / "notice.pdf"
    input_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    model_lock_path = tmp_path / "models.lock.json"
    model_lock_path.write_text("{}", encoding="utf-8")
    model_home = tmp_path / "models"
    model_home.mkdir()
    return {
        "input": input_path.resolve(),
        "output": (tmp_path / "result").resolve(),
        "model_lock": model_lock_path.resolve(),
        "model_home": model_home.resolve(),
    }


def read_log(path: Path) -> dict[str, str]:
    return {
        key: value
        for key, value in (
            line.split("=", 1)
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    }


def test_cli_reports_missing_offline_paths_as_json_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "notice.pdf"
    input_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    exit_code = cli_module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(tmp_path / "result"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    response = json.loads(captured.err)
    assert response["status"] == "FAILED"
    assert "--model-lock" in response["error"]
    assert "--model-home" in response["error"]
    assert "--uv-lock" in response["error"]


def test_cli_requires_existing_model_home(tmp_path: Path) -> None:
    arguments, _ = cli_arguments(tmp_path)
    missing_model_home = tmp_path / "models"
    missing_model_home.rmdir()
    args = cli_module.build_parser().parse_args(arguments)
    validator = getattr(cli_module, "validate_cli_paths", None)

    assert callable(validator), "validate_cli_paths() must enforce path types"
    with pytest.raises(PdfOcrError, match="model home"):
        validator(args)


def test_cli_resolves_and_passes_all_offline_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments, expected = cli_arguments(tmp_path)
    received: dict[str, Path] = {}

    def fake_extract(
        input_path: Path,
        output_dir: Path,
        *,
        model_lock_path: Path,
        model_home: Path,
        uv_lock_path: Path,
    ) -> Path:
        received.update(
            {
                "input": input_path,
                "output": output_dir,
                "model_lock": model_lock_path,
                "model_home": model_home,
                "uv_lock": uv_lock_path,
            }
        )
        return output_dir / "pdf-ocr-manifest.json"

    monkeypatch.setattr(cli_module, "extract_pdf", fake_extract)
    exit_code = cli_module.main(arguments)

    assert exit_code == 0
    assert received == expected
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "status": "SUCCEEDED",
        "manifest": str(
            expected["output"] / "pdf-ocr-manifest.json"
        ),
    }


def test_cli_writes_korean_failure_as_json_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments, _ = cli_arguments(tmp_path)

    def fail_extract(*args: object, **kwargs: object) -> Path:
        raise PdfOcrError("모델 잠금 검증 실패")

    monkeypatch.setattr(cli_module, "extract_pdf", fail_extract)
    exit_code = cli_module.main(arguments)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "status": "FAILED",
        "error": "모델 잠금 검증 실패",
    }
    assert "모델 잠금 검증 실패" in captured.err


def test_cli_configures_direct_json_streams_as_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured: list[tuple[str, str]] = []

    class ReconfigurableStream:
        def reconfigure(self, *, encoding: str, errors: str) -> None:
            configured.append((encoding, errors))

    monkeypatch.setattr(cli_module.sys, "stdout", ReconfigurableStream())
    monkeypatch.setattr(cli_module.sys, "stderr", ReconfigurableStream())

    configure = getattr(cli_module, "_configure_utf8_json_streams", None)
    assert callable(configure), "direct CLI must configure UTF-8 JSON streams"
    configure()

    assert configured == [("utf-8", "strict"), ("utf-8", "strict")]


def test_wrapper_passes_frozen_offline_runtime_and_recovery_handshake(
    tmp_path: Path,
) -> None:
    paths = wrapper_paths(tmp_path)
    environment, log_path = fake_uv_environment(tmp_path, exit_code=0)

    completed = run_wrapper(
        paths["input"],
        paths["output"],
        paths["model_lock"],
        paths["model_home"],
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "SUCCEEDED"
    log = read_log(log_path)
    assert log["HF_HUB_OFFLINE"] == "1"
    assert log["TRANSFORMERS_OFFLINE"] == "1"
    assert log["UV_OFFLINE"] == "1"
    assert Path(log["PDF_OCR_MODEL_HOME"]) == paths["model_home"]
    assert Path(log["DOCLING_ARTIFACTS_PATH"]) == paths["model_home"]
    assert re.fullmatch(r"[0-9a-f]{64}", log["RECOVERY_TOKEN"])
    assert re.fullmatch(r"[0-9a-f]{32}", log["STAGING_NONCE"])
    assert log["RECEIPT_VALUE"] == log["RECOVERY_TOKEN"]
    expected_staging = (
        paths["output"].parent
        / f".{paths['output'].name}.tmp-{log['STAGING_NONCE']}"
    )
    assert Path(log["STAGING_PATH"]) == expected_staging
    assert not Path(log["RECOVERY_RECEIPT"]).exists()
    arguments = log["ARGS"]
    assert "run --frozen --project tools/pdf-ocr" in arguments
    assert f"--input {paths['input']}" in arguments
    assert f"--output {paths['output']}" in arguments
    assert f"--model-lock {paths['model_lock']}" in arguments
    assert f"--model-home {paths['model_home']}" in arguments
    assert "--uv-lock " in arguments


def test_docker_installs_project_after_source_copy_and_is_runtime_offline() -> None:
    dockerfile = (
        REPOSITORY_ROOT / "tools" / "pdf-ocr" / "Dockerfile"
    ).read_text(encoding="utf-8")

    source_copy = dockerfile.index("COPY src ./src")
    frozen_sync = dockerfile.index("RUN uv sync --frozen --no-dev")
    runtime_offline = dockerfile.index("ENV UV_OFFLINE=1")

    assert source_copy < frozen_sync
    assert frozen_sync < runtime_offline
    assert "paddleocr" not in dockerfile.lower()
    assert "paddlepaddle" not in dockerfile.lower()
    assert "create_ocr_pipeline" not in dockerfile


@pytest.mark.parametrize("omit_owner_marker", [False, True])
def test_wrapper_cleans_only_its_exact_stage_after_abnormal_child_exit(
    tmp_path: Path,
    omit_owner_marker: bool,
) -> None:
    paths = wrapper_paths(tmp_path)
    unrelated = tmp_path / ".result.tmp-unrelated"
    environment, log_path = fake_uv_environment(
        tmp_path,
        exit_code=86,
        create_stage=True,
        omit_owner_marker=omit_owner_marker,
        other_stage=unrelated,
    )

    completed = run_wrapper(
        paths["input"],
        paths["output"],
        paths["model_lock"],
        paths["model_home"],
        environment=environment,
    )

    assert completed.returncode == 86
    log = read_log(log_path)
    assert not Path(log["STAGING_PATH"]).exists()
    assert unrelated.is_dir()
    assert (
        unrelated / STAGING_OWNER_MARKER
    ).read_text(encoding="utf-8") == "pdf-ocr-owned-staging-v1"
    assert not paths["output"].exists()


def test_wrapper_preserves_stage_from_normal_failure(tmp_path: Path) -> None:
    paths = wrapper_paths(tmp_path)
    environment, log_path = fake_uv_environment(
        tmp_path,
        exit_code=1,
        create_stage=True,
    )

    completed = run_wrapper(
        paths["input"],
        paths["output"],
        paths["model_lock"],
        paths["model_home"],
        environment=environment,
    )

    assert completed.returncode == 1
    log = read_log(log_path)
    staging = Path(log["STAGING_PATH"])
    assert staging.is_dir()
    assert (
        staging / STAGING_OWNER_MARKER
    ).read_text(encoding="utf-8") == log["RECOVERY_TOKEN"]


def test_wrapper_preserves_foreign_token_stage(tmp_path: Path) -> None:
    paths = wrapper_paths(tmp_path)
    environment, log_path = fake_uv_environment(
        tmp_path,
        exit_code=86,
        create_stage=True,
        marker_value="pdf-ocr-owned-staging-v1",
    )

    completed = run_wrapper(
        paths["input"],
        paths["output"],
        paths["model_lock"],
        paths["model_home"],
        environment=environment,
    )

    assert completed.returncode == 86
    staging = Path(read_log(log_path)["STAGING_PATH"])
    assert staging.is_dir()
    assert (
        staging / STAGING_OWNER_MARKER
    ).read_text(encoding="utf-8") == "pdf-ocr-owned-staging-v1"


def test_wrapper_preserves_stage_containing_reparse_tree(tmp_path: Path) -> None:
    paths = wrapper_paths(tmp_path)
    link_target = tmp_path / "outside"
    link_target.mkdir()
    protected = link_target / "keep.txt"
    protected.write_text("preserve", encoding="utf-8")
    environment, log_path = fake_uv_environment(
        tmp_path,
        exit_code=86,
        create_stage=True,
        link_target=link_target,
    )

    completed = run_wrapper(
        paths["input"],
        paths["output"],
        paths["model_lock"],
        paths["model_home"],
        environment=environment,
    )

    assert completed.returncode == 86
    staging = Path(read_log(log_path)["STAGING_PATH"])
    assert staging.is_dir()
    assert (staging / "linked").exists()
    assert protected.read_text(encoding="utf-8") == "preserve"


def test_pipeline_uses_exact_wrapper_staging_path_and_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "result"
    nonce = "1" * 32
    token = "2" * 64
    staging_path = tmp_path / f".result.tmp-{nonce}"
    receipt_path = tmp_path / f".result.recovery-{nonce}"
    receipt_path.write_text(token, encoding="utf-8", newline="")
    monkeypatch.setenv("PDF_OCR_RECOVERY_TOKEN", token)
    monkeypatch.setenv("PDF_OCR_STAGING_NONCE", nonce)
    monkeypatch.setenv("PDF_OCR_STAGING_PATH", str(staging_path))
    monkeypatch.setenv("PDF_OCR_RECOVERY_RECEIPT", str(receipt_path))
    parent_guard = pipeline_module._open_directory_guard(
        tmp_path,
        parent_target=True,
    )
    staging = None
    staging_guard = None
    owner_token = None
    try:
        staging, staging_guard, owner_token = (
            pipeline_module._create_private_staging(output, parent_guard)
        )
        assert staging == staging_path
        assert owner_token == token
        assert (
            staging / STAGING_OWNER_MARKER
        ).read_text(encoding="utf-8") == token
    finally:
        if (
            staging is not None
            and staging_guard is not None
            and owner_token is not None
        ):
            pipeline_module._cleanup_owned_staging(
                staging,
                staging_guard,
                parent_guard,
                owner_token,
            )
        parent_guard.close()
