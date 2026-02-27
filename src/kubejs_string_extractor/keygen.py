"""Translation key generator for extracted KubeJS strings."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from kubejs_string_extractor.extractor import ExtractedString


def _sanitize(name: str) -> str:
    """Sanitize a name for use as a translation key segment."""
    # Lowercase, replace non-alphanum with underscore, collapse multiples
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "unknown"


def _script_type(source_file: str) -> str:
    """Determine the script type from the file path."""
    # Normalize to forward slashes for consistent matching
    normalized = source_file.replace("\\", "/")
    if "/client_scripts/" in normalized:
        return "client"
    if "/server_scripts/" in normalized:
        return "server"
    if "/startup_scripts/" in normalized:
        return "startup"
    return "script"


def _file_segment(source_file: str) -> str:
    """Extract a sanitized file name segment from the source path."""
    path = PurePosixPath(source_file.replace("\\", "/"))
    stem = path.stem  # filename without extension
    return _sanitize(stem)


def generate_key(
    extracted: ExtractedString,
    index: int,
    namespace: str = "kubejs",
) -> str:
    """Generate a translation key for an extracted string.

    Format: {namespace}.{script_type}.{file_name}.{index}
    Example: kubejs.startup.universal_press.1
    """
    script_type = _script_type(extracted.source_file)
    file_seg = _file_segment(extracted.source_file)
    return f"{namespace}.{script_type}.{file_seg}.{index}"


def generate_keys(
    strings: list[ExtractedString],
    namespace: str = "kubejs",
) -> dict[str, str]:
    """Generate translation keys for a list of extracted strings.

    Groups strings by source file and assigns sequential indices per file.
    Returns a dict mapping translation_key -> original_string.
    Deduplicates: if the same string appears multiple times in the same file,
    it gets only one key.
    """
    # Group by source file
    by_file: dict[str, list[ExtractedString]] = {}
    for s in strings:
        by_file.setdefault(s.source_file, []).append(s)

    result: dict[str, str] = {}
    seen_values: dict[str, set[str]] = {}  # file -> set of already-seen values

    for source_file in sorted(by_file.keys()):
        file_strings = by_file[source_file]
        seen_values[source_file] = set()
        counter = 0

        for s in file_strings:
            if s.value in seen_values[source_file]:
                continue
            seen_values[source_file].add(s.value)
            counter += 1
            
            if s.pattern_type == "contextual_display_name":
                slug = _sanitize(s.value)
                result[f"item.kubejs.{slug}"] = s.value
                result[f"block.kubejs.{slug}"] = s.value
                result[f"fluid.kubejs.{slug}"] = s.value
            else:
                key = generate_key(s, counter, namespace)
                result[key] = s.value

    return result
