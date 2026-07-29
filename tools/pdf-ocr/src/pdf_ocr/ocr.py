from __future__ import annotations

import math
from collections.abc import Mapping, Set
from dataclasses import replace
from numbers import Real
from pathlib import Path
from typing import Any, Sequence

from .image_contract import PngContractError, validate_png_file
from .model_lock import (
    LockedArtifact,
    artifact_path,
    revalidate_locked_artifacts,
)
from .types import BBox, OcrPage, OcrToken, Point


class RapidOcrError(RuntimeError):
    pass


def _raise_rapidocr_error(context: str, error: Exception) -> RapidOcrError:
    return RapidOcrError(f"{context}: {error}")


def _locked_artifact(
    artifacts: Sequence[LockedArtifact],
    role: str,
) -> LockedArtifact:
    matches = [artifact for artifact in artifacts if artifact.role == role]
    if len(matches) != 1:
        raise RapidOcrError(f"RapidOCR requires one locked {role} artifact")
    return matches[0]


def _absolute_artifact_path(
    artifacts: Sequence[LockedArtifact],
    role: str,
) -> str:
    try:
        return str(artifact_path(artifacts, role).resolve())
    except RapidOcrError:
        raise
    except Exception as error:
        raise _raise_rapidocr_error(
            f"RapidOCR locked artifact is invalid for {role}",
            error,
        ) from error


def build_rapidocr_params(
    artifacts: Sequence[LockedArtifact],
) -> dict[str, Any]:
    try:
        revalidate_locked_artifacts(artifacts)
        from rapidocr import (
            EngineType,
            LangDet,
            LangRec,
            ModelType,
            OCRVersion,
        )

        return {
            "Global.text_score": 0.0,
            "Global.use_det": True,
            "Global.use_cls": False,
            "Global.use_rec": True,
            "Global.font_path": _absolute_artifact_path(
                artifacts,
                "rapidocr_font",
            ),
            "Global.log_level": "warning",
            "EngineConfig.onnxruntime.use_cuda": False,
            "EngineConfig.onnxruntime.use_dml": False,
            "Det.engine_type": EngineType.ONNXRUNTIME,
            "Det.lang_type": LangDet.CH,
            "Det.model_type": ModelType.MOBILE,
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.model_path": _absolute_artifact_path(
                artifacts,
                "rapidocr_det",
            ),
            "Cls.engine_type": EngineType.ONNXRUNTIME,
            "Cls.model_path": _absolute_artifact_path(
                artifacts,
                "rapidocr_cls",
            ),
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.lang_type": LangRec.KOREAN,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.model_path": _absolute_artifact_path(
                artifacts,
                "rapidocr_rec",
            ),
            "Rec.rec_keys_path": _absolute_artifact_path(
                artifacts,
                "rapidocr_rec_keys",
            ),
        }
    except RapidOcrError:
        raise
    except Exception as error:
        raise _raise_rapidocr_error(
            "RapidOCR parameters could not be built",
            error,
        ) from error


def create_rapidocr_engine(
    artifacts: Sequence[LockedArtifact],
) -> Any:
    try:
        from rapidocr import RapidOCR

        revalidate_locked_artifacts(artifacts)
        return RapidOCR(params=build_rapidocr_params(artifacts))
    except RapidOcrError:
        raise
    except Exception as error:
        raise _raise_rapidocr_error(
            "RapidOCR engine could not be created",
            error,
        ) from error


def create_rapidocr_runner(
    artifacts: Sequence[LockedArtifact],
    *,
    engine: Any | None = None,
) -> RapidOcrRunner:
    try:
        revalidate_locked_artifacts(artifacts)
        recognition_artifact = _locked_artifact(artifacts, "rapidocr_rec")
        if engine is None:
            engine = create_rapidocr_engine(artifacts)
        return RapidOcrRunner(
            engine=engine,
            model_name=recognition_artifact.name,
        )
    except RapidOcrError:
        raise
    except Exception as error:
        raise _raise_rapidocr_error(
            "RapidOCR runner could not be created",
            error,
        ) from error


def _bbox(polygon: tuple[Point, ...]) -> BBox:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _reading_order_key(token: OcrToken) -> tuple[float, float]:
    return (round(token.bbox[1] / 10.0) * 10.0, token.bbox[0])


def _materialize_ordered(value: Any, description: str) -> list[Any]:
    if isinstance(
        value,
        (str, bytes, bytearray, Mapping, Set),
    ):
        raise RapidOcrError(f"{description} must be an ordered iterable")
    try:
        iterator = iter(value)
        return list(iterator)
    except Exception as error:
        raise RapidOcrError(
            f"{description} must be an ordered iterable"
        ) from error


def _result_field(result: Any, field: str) -> list[Any]:
    try:
        value = getattr(result, field)
    except AttributeError as error:
        raise RapidOcrError(
            f"RapidOCR result is missing required attribute {field}"
        ) from error
    except Exception as error:
        raise RapidOcrError(
            f"RapidOCR result attribute {field} is invalid"
        ) from error
    return _materialize_ordered(
        value,
        f"RapidOCR result field {field}",
    )


def _normalize_polygon(box: Any) -> tuple[Point, ...]:
    points = _materialize_ordered(
        box,
        "RapidOCR coordinate sequence",
    )
    if len(points) < 4:
        raise RapidOcrError("RapidOCR polygon has fewer than four points")

    polygon: list[Point] = []
    for point in points:
        coordinates = _materialize_ordered(
            point,
            "RapidOCR coordinate point",
        )
        if len(coordinates) != 2:
            raise RapidOcrError(
                "RapidOCR coordinate point must contain exactly two values"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, Real)
            for value in coordinates
        ):
            raise RapidOcrError("RapidOCR coordinate is invalid")
        try:
            x = float(coordinates[0])
            y = float(coordinates[1])
        except (TypeError, ValueError, OverflowError) as error:
            raise RapidOcrError("RapidOCR coordinate is invalid") from error
        if not math.isfinite(x) or not math.isfinite(y):
            raise RapidOcrError("RapidOCR coordinate is invalid")
        polygon.append((x, y))
    area = abs(
        sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(
                polygon,
                polygon[1:] + polygon[:1],
                strict=True,
            )
        )
    ) / 2.0
    if not math.isfinite(area) or area <= 0:
        raise RapidOcrError(
            "RapidOCR polygon coordinates must have positive area"
        )
    return tuple(polygon)


def _normalize_confidence(score: Any) -> float:
    if isinstance(score, bool):
        raise RapidOcrError("RapidOCR confidence is invalid")
    try:
        confidence = float(score)
    except (TypeError, ValueError) as error:
        raise RapidOcrError("RapidOCR confidence is invalid") from error
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise RapidOcrError("RapidOCR confidence is invalid")
    return confidence


def _png_dimensions(image_path: Path) -> tuple[int, int]:
    try:
        return validate_png_file(image_path)
    except PngContractError as error:
        raise RapidOcrError(
            f"RapidOCR PNG decode or dimension validation failed: {error}"
        ) from error


class RapidOcrRunner:
    def __init__(self, engine: Any, model_name: str) -> None:
        self._engine = engine
        self._model_name = model_name

    def recognize(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> OcrPage:
        try:
            return self._recognize(image_path, page_number=page_number)
        except RapidOcrError:
            raise
        except Exception as error:
            raise _raise_rapidocr_error(
                "RapidOCR recognition failed",
                error,
            ) from error

    def _recognize(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> OcrPage:
        if image_path.suffix.lower() != ".png":
            raise RapidOcrError("RapidOCR accepts page PNG input only")

        width, height = _png_dimensions(image_path)
        result = self._engine(str(image_path))
        if result is None:
            raise RapidOcrError("RapidOCR result is missing")
        boxes = _result_field(result, "boxes")
        texts = _result_field(result, "txts")
        scores = _result_field(result, "scores")
        if not (len(boxes) == len(texts) == len(scores)):
            raise RapidOcrError("RapidOCR result lengths do not match")

        normalized_boxes = [_normalize_polygon(box) for box in boxes]
        normalized_scores = [
            _normalize_confidence(score)
            for score in scores
        ]

        tokens: list[OcrToken] = []
        for polygon, text, confidence in zip(
            normalized_boxes,
            texts,
            normalized_scores,
            strict=True,
        ):
            if not isinstance(text, str):
                raise RapidOcrError("RapidOCR text is invalid")
            if not text.strip():
                continue
            bbox = _bbox(polygon)
            if (
                bbox[0] < 0
                or bbox[1] < 0
                or bbox[2] > width
                or bbox[3] > height
                or bbox[0] >= bbox[2]
                or bbox[1] >= bbox[3]
            ):
                raise RapidOcrError(
                    "RapidOCR coordinates are outside the page or degenerate"
                )
            tokens.append(
                OcrToken(
                    text=text.strip(),
                    recognition_confidence=confidence,
                    polygon=polygon,
                    bbox=bbox,
                    reading_order=0,
                    model_name=self._model_name,
                    source_page_number=page_number,
                )
            )

        if not tokens:
            raise RapidOcrError("RapidOCR returned no text")

        ordered = tuple(
            replace(token, reading_order=index)
            for index, token in enumerate(
                sorted(tokens, key=_reading_order_key)
            )
        )
        return OcrPage(
            page_number=page_number,
            engine="RAPIDOCR",
            model_name=self._model_name,
            markdown="\n".join(token.text for token in ordered),
            tokens=ordered,
            raw={
                "boxes": [
                    [[point[0], point[1]] for point in polygon]
                    for polygon in normalized_boxes
                ],
                "txts": texts,
                "scores": normalized_scores,
            },
        )
