from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pdf_ocr.pipeline import PdfOcrError, extract_pdf


class _PdfOcrArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PdfOcrError(f"invalid command line: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = _PdfOcrArgumentParser(
        description="Extract evidence-preserving text from a PDF."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-lock", type=Path, required=True)
    parser.add_argument("--model-home", type=Path, required=True)
    parser.add_argument("--uv-lock", type=Path, required=True)
    return parser


def validate_cli_paths(args: argparse.Namespace) -> argparse.Namespace:
    args.input = _existing_path(args.input, "input PDF", directory=False)
    args.output = _absolute_path(args.output, "output directory")
    args.model_lock = _existing_path(
        args.model_lock,
        "model lock",
        directory=False,
    )
    args.model_home = _existing_path(
        args.model_home,
        "model home",
        directory=True,
    )
    args.uv_lock = _existing_path(
        args.uv_lock,
        "uv lock",
        directory=False,
    )
    return args


def _existing_path(
    value: Path,
    description: str,
    *,
    directory: bool,
) -> Path:
    try:
        path = Path(value).resolve(strict=True)
        valid_type = path.is_dir() if directory else path.is_file()
    except (OSError, RuntimeError) as error:
        raise PdfOcrError(f"{description} does not exist: {value}") from error
    if not valid_type:
        expected = "directory" if directory else "file"
        raise PdfOcrError(f"{description} must be an existing {expected}: {path}")
    return path


def _absolute_path(value: Path, description: str) -> Path:
    try:
        return Path(value).resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise PdfOcrError(f"{description} cannot be resolved: {value}") from error


def _configure_utf8_json_streams() -> None:
    for stream_name, stream in (
        ("stdout", sys.stdout),
        ("stderr", sys.stderr),
    ):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="strict")
        except (OSError, ValueError) as error:
            raise PdfOcrError(
                f"{stream_name} cannot be configured for UTF-8 JSON"
            ) from error


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _configure_utf8_json_streams()
        args = validate_cli_paths(build_parser().parse_args(argv))
        manifest_path = extract_pdf(
            args.input,
            args.output,
            model_lock_path=args.model_lock,
            model_home=args.model_home,
            uv_lock_path=args.uv_lock,
        )
    except PdfOcrError as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": str(error),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "status": "SUCCEEDED",
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
