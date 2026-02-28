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
    premapped_keys: dict[str, str] = field(default_factory=dict) # explicitly mapped keys


# ---------------------------------------------------------------------------
# Regex patterns for each extraction type
# ---------------------------------------------------------------------------

# .displayName('...') or .displayName("...")
_DISPLAY_NAME_RE = re.compile(
    r"""\.displayName\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)\s*\)""",
)

# A fallback for ANY freestanding string literal
_GENERIC_STRING_RE = re.compile(
    r"""(?:'([^'\\]*(?:\\.[^'\\]*)*)'|"([^"\\]*(?:\\.[^"\\]*)*)"|`([^`\\]*(?:\\.[^`\\]*)*)`)"""
)

# Text.of('...') or Text.of("...")
_TEXT_OF_RE = re.compile(
    r"""Text\.of\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# Text.red/green/blue/yellow/gold('...')  or  Text.red("...")
_TEXT_COLOR_RE = re.compile(
    r"""Text\.(?:red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# .append('...') or .append("...")  — standalone string appends
_APPEND_RE = re.compile(
    r"""\.append\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# scene.text(N, '...')  or  scene.text(N, "...")  — Ponder scenes
_SCENE_TEXT_RE = re.compile(
    r"""scene\.text\(\s*\d+\s*,\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*""",
)

# addAnnouncement("ver", "...")  — only the second string arg
_ANNOUNCEMENT_RE = re.compile(
    r"""addAnnouncement\(\s*(?:'[^']*'|"[^"]*"|`[^`]*`)\s*,\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# player.statusMessage = "..."  or  player.statusMessage = '...'
_STATUS_MSG_ASSIGN_RE = re.compile(
    r"""\.statusMessage\s*=\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*""",
)

# setStatusMessage(Text.red("..."))  or  setStatusMessage(Text.of("..."))
_SET_STATUS_MSG_RE = re.compile(
    r"""setStatusMessage\(\s*Text\.(?:of|red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)\s*\)""",
)

# .tell("...")  or  .tell('...')  — direct string tells
_TELL_DIRECT_RE = re.compile(
    r"""\.tell\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# .tell(Text.red("..."))  etc.
_TELL_TEXT_RE = re.compile(
    r"""\.tell\(\s*Text\.(?:of|red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# .respond(Text.yellow("..."))  etc.
_RESPOND_TEXT_RE = re.compile(
    r"""\.respond\(\s*Text\.(?:of|red|green|blue|yellow|gold)\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*\)""",
)

# addInformation strings — lines like: '§8Drop a §cPolymorphic...'
# These appear as array items inside addInformation calls
_ADD_INFO_STRING_RE = re.compile(
    r"""addInformation\s*\(""",
)

# Text.translate('key') — already-localized keys (just collect them)
_TRANSLATABLE_RE = re.compile(
    r"""Text\.translate\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)\s*[,)]""",
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


def _is_probable_display_name(text: str) -> bool:
    """Heuristic to determine if a string literal is nicely formatted enough to be an item name.
    
    Used only for blind extraction of generic strings when static code tracing fails.
    """
    if not _is_translatable(text):
        return False
    
    # Must start with a capital letter or a number (e.g. "Steel Rod", "10k Fluid Cell")
    if not re.match(r"^[A-Z0-9]", text):
        return False
        
    # Exclude CamelCase or snake_case technical IDs that don't have spaces
    if " " not in text:
        # If it's a single word, it should be Titlecased (e.g. "Basic") or UPPERCASE ("A").
        if not text.istitle() and not text.isupper():
            return False
            
    # Exclude typical code syntax, file paths, or namespace IDs
    if ".js" in text or ".png" in text or "kubejs:" in text or "minecraft:" in text:
        return False
        
    return True


def _unescape_js(s: str) -> str:
    """Unescape basic JS string escapes."""
    return s.replace(r"\"", '"').replace(r"\'", "'").replace(r"\\", "\\")


def _extract_match(m: re.Match[str]) -> str | None:
    """Extract the matched string from a regex match with multiple groups."""
    for raw in m.groups():
        if raw is not None:
            return _unescape_js(raw)
    return None


# Special pattern for KubeJS registries: create('id')...displayName('Name')
# This handles dynamic item/fluid creation where we CANNOT use Text.translate() 
# to avoid the BuilderBase stringification bug.
_CREATE_DISPLAY_NAME_RE = re.compile(
    r"""create\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)\s*\).*?\.displayName\(\s*(?:'([^']*)'|"([^"]*)"|`([^`]*)`)\s*\)"""
)

def _extract_match_group(m: re.Match[str], start_idx: int, end_idx: int) -> str | None:
    for i in range(start_idx, end_idx + 1):
        if m.group(i) is not None:
            return _unescape_js(m.group(i))
    return None

# ---------------------------------------------------------------------------
# Main extraction functions
# ---------------------------------------------------------------------------

def _snake_to_title_case(s: str) -> str:
    """Convert snake_case string to Title Case."""
    return " ".join(word.capitalize() for word in s.split("_") if word)

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

        # Context-aware display name extraction
        # Since we cannot know if it's an item, block, or fluid from just the line,
        # we generate all three possible key formats. They will be written to en_us.json.
        for m in _CREATE_DISPLAY_NAME_RE.finditer(line):
            item_id = _extract_match_group(m, 1, 3)
            display_name = _extract_match_group(m, 4, 6)
            
            # If there's JS string interpolation (e.g. `Incomplete ${name} Mechanism`),
            # the raw string captured by regex will be something like `Incomplete ${name} Mechanism`.
            # We can't evaluate JS variables easily, so instead let's just use the ID if available.
            # However, for the template strings, the inner ID might also be a template e.g. `${id}_mechanism`.
            # Still, if the ID is purely static, we can generate a title-cased English name.
            if item_id and "{" not in item_id and "$" not in item_id:
                # If display_name is static and clean, use it. Otherwise, fallback to title-cased ID.
                english_name = display_name if (display_name and "{" not in display_name and "$" not in display_name) else _snake_to_title_case(item_id)
                if english_name and _is_translatable(english_name):
                    result.premapped_keys[f"item.kubejs.{item_id}"] = english_name
                    result.premapped_keys[f"block.kubejs.{item_id}"] = english_name
                    result.premapped_keys[f"fluid.kubejs.{item_id}"] = english_name
                    
                    # KubeJS implicitly generates a Bucket item for every custom fluid.
                    # e.g., fluid `molten_iron` -> item `molten_iron_bucket` named `Molten Iron Bucket`
                    bucket_id = f"{item_id}_bucket"
                    bucket_name = f"{english_name} Bucket"
                    result.premapped_keys[f"item.kubejs.{bucket_id}"] = bucket_name
                    
                    
        # Wait - but for Modpack "create-stellar", both the ID and the display name are templated:
        # event.create(`${id}_mechanism`).texture(`...`).displayName(`${name} Mechanism`);
        # We MUST capture the static `mechanism("Steel")` call bindings.
        # Since parsing full JS AST is overkill, we add a heuristic:
        # Any string literal that matches Title Case (First Letter Capitalized) might be a name passed to a template.
        # We will extract them as standalone text fragments. If they get translated, great! 
        # But wait - we need their KEYS. Where would they map?
        # Actually, if KubeJS generates `item.kubejs.steel_mechanism` internally, the ONLY way our script
        # can translate it is if we generate that exact key.
        # So we MUST parse `mechanism("Steel")` -> `steel_mechanism`.
        # Instead of doing that, we will re-introduce `_DISPLAY_NAME_RE` from the old version
        # to AT LEAST capture static `.displayName("Static Name")` that are NOT chained to `create()`.
        # KubeJS still generates keys for those natively.
        # For the strictly dynamic ones (`mechanism("Basic")`), the *only* bulletproof way is to
        # literally just extract ANY string matching `[a-zA-Z]+ Mechanism` if we want to be hacky,
        # OR we just extract all generic string literals and let the user use the in-game assets output format when they play.
        # 
        # Actually, let's add `_DISPLAY_NAME_RE` back with a special prefix tag `[DISPLAY_NAME]` 
        # so the KeyGen can build `item.kubejs.{slugified}` as a best-effort blind guess.
        for m in _DISPLAY_NAME_RE.finditer(line):
            value = _extract_match(m)
            if value and _is_translatable(value):
                # Only add it if we didn't already process it via the createContext regex
                # A simple check: does value exist in premapped_keys values?
                if value not in result.premapped_keys.values():
                    result.strings.append(
                        ExtractedString(
                            value=value,
                            source_file=source_file,
                            line_number=line_idx,
                            pattern_type="contextual_display_name", # Special flag for keygen
                        )
                    )

        # Fallback: Extract generic string literals that look like display names.
        # This catches items hidden in function closures like `item("Steel Rod")`.
        for m in _GENERIC_STRING_RE.finditer(line):
            value = _extract_match(m)
            if value and _is_probable_display_name(value):
                already_extracted = any(e.value == value for e in result.strings if e.line_number == line_idx)
                if not already_extracted and value not in result.premapped_keys.values():
                    result.strings.append(
                        ExtractedString(
                            value=value,
                            source_file=source_file,
                            line_number=line_idx,
                            pattern_type="contextual_display_name", # Special flag for keygen
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
            combined.premapped_keys.update(file_result.premapped_keys)

    return combined
