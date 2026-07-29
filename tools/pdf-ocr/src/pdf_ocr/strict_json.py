from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


class StrictJsonError(ValueError):
    pass


def _object_without_duplicate_keys(
    pairs: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StrictJsonError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(
    value: str | bytes | bytearray,
    *,
    description: str = "JSON",
) -> Any:
    try:
        if isinstance(value, (bytes, bytearray)):
            text = bytes(value).decode("utf-8", errors="strict")
        elif isinstance(value, str):
            text = value
        else:
            raise TypeError("input must be UTF-8 bytes or text")
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except StrictJsonError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError) as error:
        raise StrictJsonError(f"{description} is not strict JSON: {error}") from error
