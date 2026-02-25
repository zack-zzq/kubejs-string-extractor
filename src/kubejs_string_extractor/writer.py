"""Resource pack JSON writer for extracted translations."""

from __future__ import annotations

import json
from pathlib import Path


def write_lang_json(
    translations: dict[str, str],
    output_dir: Path,
    namespace: str = "kubejs_string_extractor",
) -> Path:
    """Write translations to a Minecraft resource pack lang file.

    Creates: {output_dir}/assets/{namespace}/lang/en_us.json

    Args:
        translations: Mapping of translation_key -> english_string.
        output_dir: Root output directory.
        namespace: Resource pack namespace.

    Returns:
        Path to the written JSON file.
    """
    lang_dir = output_dir / "assets" / namespace / "lang"
    lang_dir.mkdir(parents=True, exist_ok=True)

    output_file = lang_dir / "en_us.json"

    # Sort keys for stable output
    sorted_translations = dict(sorted(translations.items()))

    output_file.write_text(
        json.dumps(sorted_translations, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return output_file
