from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path
from pathlib import PurePosixPath
from types import SimpleNamespace
from typing import Any

import fitz
import numpy as np
import pytest
from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion

from pdf_ocr.image_contract import PngContractError
from pdf_ocr.model_lock import LockedArtifact
from pdf_ocr.model_lock import LockedFile
from pdf_ocr.ocr import (
    RapidOcrError,
    RapidOcrRunner,
    build_rapidocr_params,
    create_rapidocr_engine,
    create_rapidocr_runner,
)


MODEL_NAME = "korean_PP-OCRv5_rec_mobile"
VALID_BOX = (
    (10.0, 20.0),
    (110.0, 20.0),
    (110.0, 50.0),
    (10.0, 50.0),
)


class FakeRapidResult:
    def __init__(
        self,
        *,
        boxes: Any,
        txts: Any,
        scores: Any,
    ) -> None:
        self.boxes = boxes
        self.txts = txts
        self.scores = scores


class BrokenIterable:
    def __iter__(self) -> Any:
        raise ValueError("iteration failed")


def write_png(path: Path, *, width: int = 300, height: int = 200) -> Path:
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pixmap.clear_with(255)
    pixmap.save(str(path))
    return path


def make_result(
    *,
    boxes: Any = None,
    txts: Any = None,
    scores: Any = None,
) -> FakeRapidResult:
    return FakeRapidResult(
        boxes=boxes
        if boxes is not None
        else [
            [
                [10.0, 20.0],
                [110.0, 20.0],
                [110.0, 50.0],
                [10.0, 50.0],
            ]
        ],
        txts=txts if txts is not None else ["서울특별시 고시 제2026-1호"],
        scores=scores if scores is not None else [0.87],
    )


def make_artifacts(tmp_path: Path) -> tuple[LockedArtifact, ...]:
    specs = (
        ("rapidocr_det", "ch_PP-OCRv5_det_mobile", "det.onnx"),
        ("rapidocr_cls", "ch_ppocr_mobile_v2.0_cls_mobile", "cls.onnx"),
        ("rapidocr_rec", MODEL_NAME, "rec.onnx"),
        ("rapidocr_rec_keys", "ppocrv5_korean_dict", "keys.txt"),
        ("rapidocr_font", "Noto Sans KR", "font.ttf"),
    )
    artifacts = []
    model_home = (tmp_path / "models").resolve()
    for role, name, filename in specs:
        root_relative = PurePosixPath(role)
        root = model_home / role
        path = (root / filename).resolve()
        path.parent.mkdir(parents=True)
        data = role.encode("ascii")
        path.write_bytes(data)
        locked_file = LockedFile(
            path=path,
            bytes=len(data),
            sha256=f"sha256:{hashlib.sha256(data).hexdigest()}",
            relative_path=PurePosixPath(filename),
        )
        artifacts.append(
            LockedArtifact(
                component="RAPIDOCR",
                role=role,
                name=name,
                source_url=f"https://models.example.test/{role}",
                license="TEST",
                model_home=model_home,
                root_relative_path=root_relative,
                entrypoint_relative_path=PurePosixPath(filename),
                root=root,
                path=path,
                files=(locked_file,),
            )
        )
    return tuple(artifacts)


def test_params_use_only_locked_absolute_paths_and_offline_cpu_enums(
    tmp_path: Path,
) -> None:
    artifacts = make_artifacts(tmp_path)
    role_paths = {artifact.role: str(artifact.path) for artifact in artifacts}

    params = build_rapidocr_params(artifacts)

    assert params["Global.text_score"] == 0.0
    assert params["Global.use_det"] is True
    assert params["Global.use_cls"] is False
    assert params["Global.use_rec"] is True
    assert params["EngineConfig.onnxruntime.use_cuda"] is False
    assert params["EngineConfig.onnxruntime.use_dml"] is False
    assert params["Det.engine_type"] is EngineType.ONNXRUNTIME
    assert params["Det.lang_type"] is LangDet.CH
    assert params["Det.model_type"] is ModelType.MOBILE
    assert params["Det.ocr_version"] is OCRVersion.PPOCRV5
    assert params["Cls.engine_type"] is EngineType.ONNXRUNTIME
    assert params["Cls.model_path"] == role_paths["rapidocr_cls"]
    assert params["Rec.engine_type"] is EngineType.ONNXRUNTIME
    assert params["Rec.lang_type"] is LangRec.KOREAN
    assert params["Rec.model_type"] is ModelType.MOBILE
    assert params["Rec.ocr_version"] is OCRVersion.PPOCRV5

    assert params["Det.model_path"] == role_paths["rapidocr_det"]
    assert params["Rec.model_path"] == role_paths["rapidocr_rec"]
    assert params["Rec.rec_keys_path"] == role_paths["rapidocr_rec_keys"]
    assert params["Global.font_path"] == role_paths["rapidocr_font"]
    assert all(Path(value).is_absolute() for value in role_paths.values())

    path_values = {
        value
        for key, value in params.items()
        if key.endswith(("_path", "font_path"))
    }
    assert path_values == set(role_paths.values())
    assert "Global.model_root_dir" not in params
    assert not any(
        isinstance(value, str) and value.startswith(("http://", "https://"))
        for value in params.values()
    )


def test_missing_locked_factory_role_is_normalized(tmp_path: Path) -> None:
    artifacts = tuple(
        artifact
        for artifact in make_artifacts(tmp_path)
        if artifact.role != "rapidocr_font"
    )

    with pytest.raises(RapidOcrError, match="rapidocr_font"):
        build_rapidocr_params(artifacts)


def test_factory_passes_locked_params_without_downloading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = make_artifacts(tmp_path)
    sentinel = object()
    captured: dict[str, Any] = {}

    def fake_rapidocr(*, params: dict[str, Any]) -> object:
        captured["params"] = params
        return sentinel

    monkeypatch.setattr("rapidocr.RapidOCR", fake_rapidocr)

    assert create_rapidocr_engine(artifacts) is sentinel
    assert captured["params"] == build_rapidocr_params(artifacts)


def test_factory_exception_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_factory(*, params: dict[str, Any]) -> None:
        raise ValueError("factory failed")

    monkeypatch.setattr("rapidocr.RapidOCR", fail_factory)

    with pytest.raises(RapidOcrError, match="factory failed"):
        create_rapidocr_engine(make_artifacts(tmp_path))


def test_factory_does_not_catch_base_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt_factory(*, params: dict[str, Any]) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("rapidocr.RapidOCR", interrupt_factory)

    with pytest.raises(KeyboardInterrupt):
        create_rapidocr_engine(make_artifacts(tmp_path))


def test_runner_factory_uses_locked_recognition_model_name(tmp_path: Path) -> None:
    image = write_png(tmp_path / "0003.png")
    engine = lambda _: make_result()

    runner = create_rapidocr_runner(make_artifacts(tmp_path), engine=engine)
    result = runner.recognize(image, page_number=3)

    assert result.model_name == MODEL_NAME
    assert result.tokens[0].model_name == MODEL_NAME


def test_params_revalidate_locked_files_before_consuming_paths(
    tmp_path: Path,
) -> None:
    artifacts = make_artifacts(tmp_path)
    artifacts[0].path.write_bytes(b"tampered")

    with pytest.raises(RapidOcrError, match="locked|model|size|SHA"):
        build_rapidocr_params(artifacts)


def test_injected_runner_revalidates_before_consuming_model_name(
    tmp_path: Path,
) -> None:
    artifacts = make_artifacts(tmp_path)
    rec_index = next(
        index
        for index, artifact in enumerate(artifacts)
        if artifact.role == "rapidocr_rec"
    )
    forged = replace(artifacts[rec_index], name="forged-name")
    tampered = list(artifacts)
    tampered[rec_index] = forged
    forged.path.write_bytes(b"tampered")

    with pytest.raises(RapidOcrError, match="locked|model|size|SHA"):
        create_rapidocr_runner(tuple(tampered), engine=lambda _: make_result())


def test_jpeg_bytes_renamed_png_are_rejected_before_engine_call(
    tmp_path: Path,
) -> None:
    from PIL import Image

    image_path = tmp_path / "renamed.png"
    Image.new("RGB", (20, 10), "white").save(image_path, format="JPEG")
    runner = RapidOcrRunner(
        engine=lambda _: pytest.fail("engine must not be called"),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="PNG"):
        runner.recognize(image_path, page_number=1)


def test_oriented_png_is_rejected_before_engine_call(tmp_path: Path) -> None:
    from PIL import Image

    image_path = tmp_path / "oriented.png"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (20, 10), "white").save(
        image_path,
        format="PNG",
        exif=exif,
    )
    runner = RapidOcrRunner(
        engine=lambda _: pytest.fail("engine must not be called"),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="orientation|PNG"):
        runner.recognize(image_path, page_number=1)


def test_runner_preserves_polygon_bbox_confidence_page_and_raw_json(
    tmp_path: Path,
) -> None:
    image = write_png(tmp_path / "0003.png")
    runner = RapidOcrRunner(engine=lambda _: make_result(), model_name=MODEL_NAME)

    result = runner.recognize(image, page_number=3)

    assert result.page_number == 3
    assert result.engine == "RAPIDOCR"
    assert result.model_name == MODEL_NAME
    assert result.markdown == "서울특별시 고시 제2026-1호"
    assert result.tokens[0].text == "서울특별시 고시 제2026-1호"
    assert result.tokens[0].recognition_confidence == 0.87
    assert result.tokens[0].polygon == (
        (10.0, 20.0),
        (110.0, 20.0),
        (110.0, 50.0),
        (10.0, 50.0),
    )
    assert result.tokens[0].bbox == (10.0, 20.0, 110.0, 50.0)
    assert result.tokens[0].reading_order == 0
    assert result.tokens[0].source_page_number == 3
    assert result.raw == {
        "boxes": [
            [
                [10.0, 20.0],
                [110.0, 20.0],
                [110.0, 50.0],
                [10.0, 50.0],
            ]
        ],
        "txts": ["서울특별시 고시 제2026-1호"],
        "scores": [0.87],
    }
    assert json.loads(json.dumps(result.raw, allow_nan=False)) == result.raw


@pytest.mark.parametrize(
    ("boxes", "txts", "scores"),
    (
        ([], [], []),
        (
            [
                [
                    [10.0, 20.0],
                    [110.0, 20.0],
                    [110.0, 50.0],
                    [10.0, 50.0],
                ]
            ],
            [""],
            [0.87],
        ),
    ),
    ids=("empty-result", "blank-text"),
)
def test_empty_ocr_text_is_rejected(
    tmp_path: Path,
    boxes: Any,
    txts: Any,
    scores: Any,
) -> None:
    image = write_png(tmp_path / "empty.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(boxes=boxes, txts=txts, scores=scores),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="no text"):
        runner.recognize(image, page_number=1)


def test_result_length_mismatch_is_rejected(tmp_path: Path) -> None:
    image = write_png(tmp_path / "mismatch.png")
    result = make_result(txts=["first", "second"])
    runner = RapidOcrRunner(engine=lambda _: result, model_name=MODEL_NAME)

    with pytest.raises(RapidOcrError, match="length"):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize(
    ("field", "scalar"),
    (
        ("txts", "A"),
        ("txts", b"A"),
        ("txts", bytearray(b"A")),
        ("scores", "1"),
        ("scores", b"1"),
        ("scores", bytearray(b"1")),
    ),
)
def test_scalar_text_and_bytes_result_fields_are_rejected(
    tmp_path: Path,
    field: str,
    scalar: Any,
) -> None:
    image = write_png(tmp_path / f"scalar-{field}.png")
    values = {
        "boxes": [VALID_BOX],
        "txts": ["A"],
        "scores": [1.0],
    }
    values[field] = scalar
    runner = RapidOcrRunner(
        engine=lambda _: FakeRapidResult(**values),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match=field):
        runner.recognize(image, page_number=1)


def test_none_result_is_rejected_explicitly(tmp_path: Path) -> None:
    image = write_png(tmp_path / "none-result.png")
    runner = RapidOcrRunner(engine=lambda _: None, model_name=MODEL_NAME)

    with pytest.raises(RapidOcrError, match="result"):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize("missing_field", ("boxes", "txts", "scores"))
def test_missing_result_attribute_is_rejected(
    tmp_path: Path,
    missing_field: str,
) -> None:
    image = write_png(tmp_path / f"missing-{missing_field}.png")
    values = {
        "boxes": [VALID_BOX],
        "txts": ["A"],
        "scores": [1.0],
    }
    del values[missing_field]
    runner = RapidOcrRunner(
        engine=lambda _: SimpleNamespace(**values),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match=missing_field):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize("field", ("boxes", "txts", "scores"))
@pytest.mark.parametrize("invalid_value", (None, 1, object()))
def test_non_iterable_result_field_is_rejected(
    tmp_path: Path,
    field: str,
    invalid_value: Any,
) -> None:
    image = write_png(tmp_path / f"non-iterable-{field}.png")
    values = {
        "boxes": [VALID_BOX],
        "txts": ["A"],
        "scores": [1.0],
    }
    values[field] = invalid_value
    runner = RapidOcrRunner(
        engine=lambda _: FakeRapidResult(**values),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match=field):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("boxes", {VALID_BOX: "box"}),
        ("boxes", {VALID_BOX}),
        ("txts", {"A": "text"}),
        ("txts", {"A"}),
        ("scores", {1.0: "score"}),
        ("scores", {1.0}),
    ),
    ids=(
        "boxes-mapping",
        "boxes-set",
        "txts-mapping",
        "txts-set",
        "scores-mapping",
        "scores-set",
    ),
)
def test_unordered_result_container_is_rejected(
    tmp_path: Path,
    field: str,
    invalid_value: Any,
) -> None:
    image = write_png(tmp_path / f"unordered-{field}.png")
    values = {
        "boxes": [VALID_BOX],
        "txts": ["A"],
        "scores": [1.0],
    }
    values[field] = invalid_value
    runner = RapidOcrRunner(
        engine=lambda _: FakeRapidResult(**values),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match=field):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize("field", ("boxes", "txts", "scores"))
def test_result_field_iteration_failure_is_normalized(
    tmp_path: Path,
    field: str,
) -> None:
    image = write_png(tmp_path / f"iteration-{field}.png")
    values = {
        "boxes": [VALID_BOX],
        "txts": ["A"],
        "scores": [1.0],
    }
    values[field] = BrokenIterable()
    runner = RapidOcrRunner(
        engine=lambda _: FakeRapidResult(**values),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match=field):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize("container_type", ("list", "tuple", "ndarray"))
def test_ordered_rapidocr_result_containers_are_accepted(
    tmp_path: Path,
    container_type: str,
) -> None:
    image = write_png(tmp_path / f"ordered-{container_type}.png")
    values: dict[str, Any] = {
        "boxes": [VALID_BOX],
        "txts": ["A"],
        "scores": [1.0],
    }
    if container_type == "tuple":
        values = {
            "boxes": (VALID_BOX,),
            "txts": ("A",),
            "scores": (1.0,),
        }
    elif container_type == "ndarray":
        values = {
            "boxes": np.asarray([VALID_BOX], dtype=np.float32),
            "txts": np.asarray(["A"]),
            "scores": np.asarray([1.0], dtype=np.float32),
        }
    runner = RapidOcrRunner(
        engine=lambda _: FakeRapidResult(**values),
        model_name=MODEL_NAME,
    )

    result = runner.recognize(image, page_number=1)

    assert result.tokens[0].text == "A"
    assert result.tokens[0].recognition_confidence == 1.0


@pytest.mark.parametrize(
    "confidence",
    (float("nan"), float("inf"), -0.01, 1.01, "not-a-number"),
)
def test_invalid_confidence_is_rejected(
    tmp_path: Path,
    confidence: Any,
) -> None:
    image = write_png(tmp_path / "confidence.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(scores=[confidence]),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="confidence"):
        runner.recognize(image, page_number=1)


def test_boolean_confidence_is_rejected(tmp_path: Path) -> None:
    image = write_png(tmp_path / "boolean-confidence.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(scores=[True]),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="confidence"):
        runner.recognize(image, page_number=1)


def test_polygon_with_fewer_than_four_points_is_rejected(tmp_path: Path) -> None:
    image = write_png(tmp_path / "polygon.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(
            boxes=[[[10, 10], [20, 10], [20, 20]]],
        ),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="fewer than four"):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize(
    "point",
    (
        [10],
        [10, 20, 30],
        "12",
        b"12",
        bytearray(b"12"),
        {0: 10, 1: 20},
        {10, 20},
    ),
)
def test_polygon_point_must_be_an_ordered_pair(
    tmp_path: Path,
    point: Any,
) -> None:
    image = write_png(tmp_path / "point.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(
            boxes=[
                [
                    point,
                    [110, 20],
                    [110, 50],
                    [10, 50],
                ]
            ],
        ),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="coordinate"):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize(
    "coordinate",
    (
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        "not-a-number",
        None,
        object(),
    ),
)
def test_non_numeric_coordinate_is_rejected(
    tmp_path: Path,
    coordinate: Any,
) -> None:
    image = write_png(tmp_path / "coordinate.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(
            boxes=[
                [
                    [coordinate, 10],
                    [20, 10],
                    [20, 20],
                    [10, 20],
                ]
            ],
        ),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="coordinate"):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize(
    "box",
    (
        [[-1, 10], [20, 10], [20, 20], [-1, 20]],
        [[10, 10], [301, 10], [301, 20], [10, 20]],
        [[10, 10], [10, 10], [10, 20], [10, 20]],
        [[10, 10], [20, 10], [20, 10], [10, 10]],
    ),
    ids=("negative", "past-page", "zero-width", "zero-height"),
)
def test_outside_or_degenerate_bbox_is_rejected(
    tmp_path: Path,
    box: list[list[float]],
) -> None:
    image = write_png(tmp_path / "bbox.png")
    runner = RapidOcrRunner(
        engine=lambda _: make_result(boxes=[box]),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="coordinates"):
        runner.recognize(image, page_number=1)


def test_non_png_input_is_rejected_before_engine_call(tmp_path: Path) -> None:
    image = tmp_path / "page.jpg"

    def unexpected_engine(_: str) -> None:
        raise AssertionError("engine must not be called")

    runner = RapidOcrRunner(engine=unexpected_engine, model_name=MODEL_NAME)

    with pytest.raises(RapidOcrError, match="PNG"):
        runner.recognize(image, page_number=1)


def test_corrupted_png_is_normalized(tmp_path: Path) -> None:
    image = tmp_path / "corrupted.png"
    image.write_bytes(b"not a PNG image")
    runner = RapidOcrRunner(
        engine=lambda _: pytest.fail("engine must not be called"),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="PNG"):
        runner.recognize(image, page_number=1)


@pytest.mark.parametrize(
    ("width", "height"),
    ((0, 200), (-1, 200), (300, 0), (300, -1)),
)
def test_non_positive_png_dimensions_are_rejected_before_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    width: int,
    height: int,
) -> None:
    image = tmp_path / "dimension.png"
    image.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "pdf_ocr.ocr.validate_png_file",
        lambda _: (_ for _ in ()).throw(
            PngContractError(
                f"PNG dimensions must be positive: {width}x{height}"
            )
        ),
    )
    runner = RapidOcrRunner(
        engine=lambda _: pytest.fail("engine must not be called"),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="dimension"):
        runner.recognize(image, page_number=1)


def test_png_dimension_access_failure_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "broken-dimension.png"
    image.write_bytes(b"placeholder")
    monkeypatch.setattr(
        "pdf_ocr.ocr.validate_png_file",
        lambda _: (_ for _ in ()).throw(
            PngContractError("dimension unavailable")
        ),
    )
    runner = RapidOcrRunner(
        engine=lambda _: pytest.fail("engine must not be called"),
        model_name=MODEL_NAME,
    )

    with pytest.raises(RapidOcrError, match="dimension"):
        runner.recognize(image, page_number=1)


def test_png_decode_does_not_catch_base_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "interrupt-decode.png"
    image.write_bytes(b"placeholder")

    def interrupt_decode(_: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("pdf_ocr.ocr.validate_png_file", interrupt_decode)
    runner = RapidOcrRunner(
        engine=lambda _: pytest.fail("engine must not be called"),
        model_name=MODEL_NAME,
    )

    with pytest.raises(KeyboardInterrupt):
        runner.recognize(image, page_number=1)


def test_reading_order_uses_y_band_then_x_and_preserves_raw_order(
    tmp_path: Path,
) -> None:
    image = write_png(tmp_path / "order.png")
    source = FakeRapidResult(
        boxes=[
            [[100, 11], [140, 11], [140, 21], [100, 21]],
            [[20, 14], [60, 14], [60, 24], [20, 24]],
            [[10, 31], [50, 31], [50, 41], [10, 41]],
        ],
        txts=["right", "left", "next-line"],
        scores=[0.91, 0.92, 0.93],
    )
    runner = RapidOcrRunner(engine=lambda _: source, model_name=MODEL_NAME)

    result = runner.recognize(image, page_number=1)

    assert [token.text for token in result.tokens] == [
        "left",
        "right",
        "next-line",
    ]
    assert [token.reading_order for token in result.tokens] == [0, 1, 2]
    assert result.markdown == "left\nright\nnext-line"
    assert result.raw["txts"] == ["right", "left", "next-line"]


def test_runner_exception_is_normalized(tmp_path: Path) -> None:
    image = write_png(tmp_path / "engine-error.png")

    def fail_engine(_: str) -> None:
        raise ValueError("engine failed")

    runner = RapidOcrRunner(engine=fail_engine, model_name=MODEL_NAME)

    with pytest.raises(RapidOcrError, match="engine failed"):
        runner.recognize(image, page_number=1)


def test_runner_does_not_catch_base_exceptions(tmp_path: Path) -> None:
    image = write_png(tmp_path / "interrupt.png")

    def interrupt_engine(_: str) -> None:
        raise SystemExit(9)

    runner = RapidOcrRunner(engine=interrupt_engine, model_name=MODEL_NAME)

    with pytest.raises(SystemExit, match="9"):
        runner.recognize(image, page_number=1)
