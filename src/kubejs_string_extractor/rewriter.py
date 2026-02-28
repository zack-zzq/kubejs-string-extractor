"""Rewriter module that modifies KubeJS files to use Text.translate() calls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kubejs_string_extractor.extractor import _is_translatable, _unescape_js


@dataclass
class RewriteResult:
    """Result of rewriting a file."""

    original_path: Path
    modified_content: str
    replacements_made: int


# ---------------------------------------------------------------------------
# Replacement functions for each pattern type
# ---------------------------------------------------------------------------


def _build_replacer(string_to_key: dict[str, str]):
    """Build a replacer function that maps string values to their translation keys."""

    def _get_key(raw: str) -> str | None:
        value = _unescape_js(raw)
        return string_to_key.get(value)

    return _get_key


def _replace_display_name(line: str, get_key) -> str:
    """Replace .displayName('...') with .displayName(Text.translate('key'))."""

    def replacer(m: re.Match) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f".displayName(Text.translate('{key}'))"

    return re.sub(
        r"""\.displayName\(\s*(?:'([^']*)'|"([^"]*)")\s*\)""",
        replacer,
        line,
    )


def _replace_text_of(line: str, get_key) -> str:
    """Replace Text.of('...') with Text.translate('key')."""

    def replacer(m: re.Match) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f"Text.translate('{key}')"

    return re.sub(
        r"""Text\.of\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
        replacer,
        line,
    )


def _replace_text_color(line: str, get_key) -> str:
    """Replace Text.red('...') with Text.translate('key').red() etc."""

    def replacer(m: re.Match) -> str:
        color = m.group(1)
        raw = m.group(2) if m.group(2) is not None else m.group(3)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f"Text.translate('{key}').{color}()"

    return re.sub(
        r"""Text\.(red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
        replacer,
        line,
    )


def _replace_append(line: str, get_key) -> str:
    """Replace .append('...') with .append(Text.translate('key'))."""

    def replacer(m: re.Match) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f".append(Text.translate('{key}'))"

    return re.sub(
        r"""\.append\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
        replacer,
        line,
    )


def _replace_scene_text(line: str, get_key) -> str:
    """Replace scene.text(N, '...') with scene.text(N, Text.translate('key'))."""

    def replacer(m: re.Match) -> str:
        number = m.group(1)
        raw = m.group(2) if m.group(2) is not None else m.group(3)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f"scene.text({number}, Text.translate('{key}')"

    return re.sub(
        r"""scene\.text\(\s*(\d+)\s*,\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*""",
        replacer,
        line,
    )


def _replace_announcement(line: str, get_key) -> str:
    """Replace addAnnouncement("ver", "...") with addAnnouncement("ver", Text.translate('key'))."""

    def replacer(m: re.Match) -> str:
        version_part = m.group(1)
        raw = m.group(2) if m.group(2) is not None else m.group(3)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f"addAnnouncement({version_part}, Text.translate('{key}'))"

    return re.sub(
        r"""addAnnouncement\(\s*('[^']*'|"[^"]*")\s*,\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
        replacer,
        line,
    )


def _replace_status_message_assign(line: str, get_key) -> str:
    """Replace .statusMessage = "..." with .statusMessage = Text.translate('key')."""

    def replacer(m: re.Match) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f".statusMessage = Text.translate('{key}')"

    return re.sub(
        r"""\.statusMessage\s*=\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""",
        replacer,
        line,
    )


def _replace_tell_direct(line: str, get_key) -> str:
    """Replace .tell("...") with .tell(Text.translate('key'))."""

    def replacer(m: re.Match) -> str:
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        key = get_key(raw)
        if key is None:
            return m.group(0)
        return f".tell(Text.translate('{key}'))"

    return re.sub(
        r"""\.tell\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
        replacer,
        line,
    )


# Note: .tell(Text.red("...")) and .respond(Text.yellow("...")) are
# handled by _replace_text_color since it replaces the inner Text.red() etc.
# The outer .tell()/.respond() doesn't need changing.


# ---------------------------------------------------------------------------
# Ordered list of replacement functions
# ---------------------------------------------------------------------------

_REPLACERS = [
    _replace_display_name,
    _replace_text_of,
    _replace_text_color,
    _replace_append,
    _replace_scene_text,
    _replace_announcement,
    _replace_status_message_assign,
    _replace_tell_direct,
]


# ---------------------------------------------------------------------------
# Main rewrite functions
# ---------------------------------------------------------------------------


def rewrite_content(
    content: str,
    string_to_key: dict[str, str],
) -> tuple[str, int]:
    """Rewrite a JS file's content, replacing hardcoded strings with Text.translate().

    Args:
        content: Original file content.
        string_to_key: Mapping of original string value -> translation key.

    Returns:
        Tuple of (modified_content, number_of_replacements).
    """
    get_key = _build_replacer(string_to_key)
    lines = content.splitlines(keepends=True)
    total_replacements = 0

    for i, line in enumerate(lines):
        # Skip comment-only lines
        if line.strip().startswith("//"):
            continue

        original_line = line
        for replacer_fn in _REPLACERS:
            line = replacer_fn(line, get_key)
        lines[i] = line

        if line != original_line:
            total_replacements += 1

    return "".join(lines), total_replacements


def rewrite_file(
    filepath: Path,
    string_to_key: dict[str, str],
    output_dir: Path | None = None,
) -> RewriteResult | None:
    """Rewrite a single JS file, replacing hardcoded strings with Text.translate().

    Args:
        filepath: Path to the original JS file.
        string_to_key: Mapping of original string value -> translation key.
        output_dir: If provided, write modified file here (mirroring structure).
                   If None, modify in place.

    Returns:
        RewriteResult if changes were made, None otherwise.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = filepath.read_text(encoding="utf-8", errors="replace")

    modified_content, replacements = rewrite_content(content, string_to_key)

    if replacements == 0:
        return None

    if output_dir is not None:
        # Mirror the file structure under output_dir
        output_path = output_dir / filepath.name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(modified_content, encoding="utf-8")
    else:
        filepath.write_text(modified_content, encoding="utf-8")

    return RewriteResult(
        original_path=filepath,
        modified_content=modified_content,
        replacements_made=replacements,
    )


def rewrite_directory(
    kubejs_dir: Path,
    string_to_key: dict[str, str],
    output_dir: Path | None = None,
) -> list[RewriteResult]:
    """Rewrite all JS files in a KubeJS directory.

    Args:
        kubejs_dir: Path to the kubejs directory.
        string_to_key: Mapping of original string value -> translation key.
        output_dir: If provided, write modified files here.
                   If None, modify files in place.
    """
    results: list[RewriteResult] = []

    script_dirs = ["client_scripts", "server_scripts", "startup_scripts"]

    for script_dir_name in script_dirs:
        script_dir = kubejs_dir / script_dir_name
        if not script_dir.exists():
            continue

        for js_file in sorted(script_dir.rglob("*.js")):
            # Compute relative path for output mirroring
            rel_path = js_file.relative_to(kubejs_dir)
            out_dir = (output_dir / rel_path.parent) if output_dir else None

            result = rewrite_file(js_file, string_to_key, out_dir)
            if result is not None:
                results.append(result)

    return results
