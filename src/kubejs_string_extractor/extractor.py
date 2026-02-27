"""Core extraction engine for finding translatable strings in KubeJS scripts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractedString:
    """A single extracted translatable string."""

    value: str
    source_file: str
    line_number: int
    pattern_type: str  # e.g. 'displayName', 'Text.of', 'scene.text', etc.


@dataclass
class ExtractionResult:
    """Result of extracting strings from a KubeJS directory."""

    strings: list[ExtractedString] = field(default_factory=list)
    translatable_keys: list[str] = field(default_factory=list)  # already-localized keys


# ---------------------------------------------------------------------------
# Regex patterns for each extraction type
# ---------------------------------------------------------------------------

# .displayName('...') or .displayName("...")
_DISPLAY_NAME_RE = re.compile(
    r"""\.displayName\(\s*(?:'([^']*)'|"([^"]*)")\s*\)""",
)

# Text.of('...') or Text.of("...")
_TEXT_OF_RE = re.compile(
    r"""Text\.of\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# Text.red/green/blue/yellow/gold('...')  or  Text.red("...")
_TEXT_COLOR_RE = re.compile(
    r"""Text\.(?:red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# .append('...') or .append("...")  — standalone string appends
_APPEND_RE = re.compile(
    r"""\.append\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# scene.text(N, '...')  or  scene.text(N, "...")  — Ponder scenes
_SCENE_TEXT_RE = re.compile(
    r"""scene\.text\(\s*\d+\s*,\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*""",
)

# addAnnouncement("ver", "...")  — only the second string arg
_ANNOUNCEMENT_RE = re.compile(
    r"""addAnnouncement\(\s*(?:'[^']*'|"[^"]*")\s*,\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# player.statusMessage = "..."  or  player.statusMessage = '...'
_STATUS_MSG_ASSIGN_RE = re.compile(
    r"""\.statusMessage\s*=\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*""",
)

# setStatusMessage(Text.red("..."))  or  setStatusMessage(Text.of("..."))
_SET_STATUS_MSG_RE = re.compile(
    r"""setStatusMessage\(\s*Text\.(?:of|red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)\s*\)""",
)

# .tell("...")  or  .tell('...')  — direct string tells
_TELL_DIRECT_RE = re.compile(
    r"""\.tell\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# .tell(Text.red("..."))  etc.
_TELL_TEXT_RE = re.compile(
    r"""\.tell\(\s*Text\.(?:of|red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# .respond(Text.yellow("..."))  etc.
_RESPOND_TEXT_RE = re.compile(
    r"""\.respond\(\s*Text\.(?:of|red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""",
)

# addInformation strings — lines like: '§8Drop a §cPolymorphic...'
# These appear as array items inside addInformation calls
_ADD_INFO_STRING_RE = re.compile(
    r"""addInformation\s*\(""",
)

# Text.translate('key') — already-localized keys (just collect them)
_TRANSLATABLE_RE = re.compile(
    r"""Text\.translatable\(\s*(?:'([^']*)'|"([^"]*)")\s*[,)]""",
)


# ---------------------------------------------------------------------------
# Patterns list for iteration
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("displayName", _DISPLAY_NAME_RE),
    ("Text.of", _TEXT_OF_RE),
    ("Text.color", _TEXT_COLOR_RE),
    ("append", _APPEND_RE),
    ("scene.text", _SCENE_TEXT_RE),
    ("announcement", _ANNOUNCEMENT_RE),
    ("statusMessage", _STATUS_MSG_ASSIGN_RE),
    ("setStatusMessage", _SET_STATUS_MSG_RE),
    ("tell", _TELL_DIRECT_RE),
    ("tell.Text", _TELL_TEXT_RE),
    ("respond.Text", _RESPOND_TEXT_RE),
]


# ---------------------------------------------------------------------------
# Filtering heuristics
# ---------------------------------------------------------------------------

# Minecraft formatting codes: §0-§9, §a-§f, §k-§o, §r
_FORMATTING_CODE_RE = re.compile(r"§[0-9a-fk-or]")

# Item/block ID pattern: namespace:path (no spaces)
_ITEM_ID_RE = re.compile(r"^[a-z_][a-z0-9_]*:[a-z0-9_./]+$")


def _is_translatable(s: str) -> bool:
    """Return True if the string is meaningful and worth translating."""
    if not s or not s.strip():
        return False

    # Strip Minecraft formatting codes to see what remains
    stripped = _FORMATTING_CODE_RE.sub("", s).strip()

    if not stripped:
        return False

    # Skip item/block IDs  (e.g. 'minecraft:oak_sign')
    if _ITEM_ID_RE.match(s.strip()):
        return False

    # Skip pure formatting blocks (colored squares for structure guides)
    # These are strings like "§0███§7███§0███"
    letter_content = re.sub(r"[█▓░\s]", "", stripped)
    if not letter_content:
        return False

    # Skip very short strings (single chars, just punctuation)
    if len(stripped) <= 1 and not stripped.isalpha():
        return False

    return True


def _unescape_js(s: str) -> str:
    """Unescape basic JS string escapes."""
    return s.replace(r"\"", '"').replace(r"\'", "'").replace(r"\\", "\\")


def _extract_match(m: re.Match[str]) -> str | None:
    """Extract the matched string from a regex match with two groups (single/double quote)."""
    raw = m.group(1) if m.group(1) is not None else m.group(2)
    if raw is None:
        return None
    return _unescape_js(raw)


# ---------------------------------------------------------------------------
# Main extraction functions
# ---------------------------------------------------------------------------


def extract_from_content(
    content: str,
    source_file: str,
) -> ExtractionResult:
    """Extract translatable strings from a single JS file's content."""
    result = ExtractionResult()

    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        # Skip comment-only lines
        stripped_line = line.strip()
        if stripped_line.startswith("//"):
            continue

        # Extract translatable keys (already localized)
        for m in _TRANSLATABLE_RE.finditer(line):
            key = _extract_match(m)
            if key and not key.startswith("[") and not key.startswith("="):
                result.translatable_keys.append(key)

        # Extract hardcoded strings
        for pattern_name, pattern in _PATTERNS:
            for m in pattern.finditer(line):
                value = _extract_match(m)
                if value and _is_translatable(value):
                    result.strings.append(
                        ExtractedString(
                            value=value,
                            source_file=source_file,
                            line_number=line_idx,
                            pattern_type=pattern_name,
                        )
                    )

    return result


def extract_from_file(filepath: Path) -> ExtractionResult:
    """Extract translatable strings from a single JS file."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    return extract_from_content(content, str(filepath))


def extract_from_directory(kubejs_dir: Path) -> ExtractionResult:
    """Extract translatable strings from all JS files in a KubeJS directory.

    Scans client_scripts/, server_scripts/, and startup_scripts/.
    """
    combined = ExtractionResult()

    script_dirs = ["client_scripts", "server_scripts", "startup_scripts"]

    for script_dir_name in script_dirs:
        script_dir = kubejs_dir / script_dir_name
        if not script_dir.exists():
            continue

        for js_file in sorted(script_dir.rglob("*.js")):
            file_result = extract_from_file(js_file)
            combined.strings.extend(file_result.strings)
            combined.translatable_keys.extend(file_result.translatable_keys)

    return combined
