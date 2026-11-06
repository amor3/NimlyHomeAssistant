"""Every translation has the keys and placeholders of strings.json."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components" / "nimly_digital_lock"
TRANSLATIONS = sorted((COMPONENT / "translations").glob("*.json"))
_PLACEHOLDER = re.compile(r"\{\w+\}")


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        else:
            flat[path] = value
    return flat


STRINGS = _flatten(json.loads((COMPONENT / "strings.json").read_text()))


def test_english_matches_strings() -> None:
    assert _flatten(json.loads((COMPONENT / "translations" / "en.json").read_text())) == STRINGS


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda p: p.stem)
def test_translation_complete(path: Path) -> None:
    translated = _flatten(json.loads(path.read_text()))
    assert set(translated) == set(STRINGS)
    for key, text in STRINGS.items():
        assert set(_PLACEHOLDER.findall(translated[key])) == set(_PLACEHOLDER.findall(text)), key
