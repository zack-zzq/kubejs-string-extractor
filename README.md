# KubeJS String Extractor

Extract translatable strings from Minecraft modpack KubeJS scripts, rewrite the JS files to use `Text.translatable()`, and output `en_us.json` lang files for localization.

## What it does

KubeJS scripts often contain hardcoded English strings (item names, tooltips, ponder text, announcements, etc.) that are not translatable via standard Minecraft resource packs. This tool:

1. **Scans** `client_scripts/`, `server_scripts/`, and `startup_scripts/` for translatable strings
2. **Extracts** strings from patterns like `.displayName()`, `Text.of()`, `Text.red()`, `scene.text()`, `addAnnouncement()`, etc.
3. **Rewrites** the original JS files to use `Text.translatable('key')` calls
4. **Outputs** a standard `en_us.json` lang file for translators to work with

## Supported Patterns

| Original | Rewritten As |
|---|---|
| `.displayName('Foo')` | `.displayName(Text.translatable('key'))` |
| `Text.of('Foo')` | `Text.translatable('key')` |
| `Text.red('Foo')` | `Text.translatable('key').red()` |
| `Text.green/blue/yellow/gold('Foo')` | `Text.translatable('key').green/blue/yellow/gold()` |
| `scene.text(N, 'Foo', ...)` | `scene.text(N, Text.translatable('key'), ...)` |
| `addAnnouncement("ver", "Foo")` | `addAnnouncement("ver", Text.translatable('key'))` |
| `.append('Foo')` | `.append(Text.translatable('key'))` |
| `.statusMessage = "Foo"` | `.statusMessage = Text.translatable('key')` |
| `.tell("Foo")` | `.tell(Text.translatable('key'))` |

## Installation

```bash
pip install kubejs-string-extractor
```

Or with uv:

```bash
uv tool install kubejs-string-extractor
```

## Usage

```bash
# Extract strings, rewrite JS files, and generate en_us.json
kubejs-strings extract path/to/kubejs

# Custom output directory
kubejs-strings extract path/to/kubejs --output my_translations

# Extract only (no JS rewriting)
kubejs-strings extract path/to/kubejs --no-rewrite

# Modify original JS files in place (⚠️ make backups first!)
kubejs-strings extract path/to/kubejs --in-place

# Custom namespace prefix for translation keys
kubejs-strings extract path/to/kubejs --namespace mypack
```

### Output

```
extracted/
├── assets/
│   └── kubejs_string_extractor/
│       └── lang/
│           └── en_us.json          # Translation keys → English strings
└── kubejs/                         # Rewritten JS files (unless --no-rewrite)
    ├── client_scripts/
    ├── server_scripts/
    └── startup_scripts/
```

The `en_us.json` contains entries like:

```json
{
  "kubejs.client.tooltips.1": "Place the pad down in the specified Dimension",
  "kubejs.startup.universal_press.1": "Inscriber Universal Press"
}
```

### Workflow

1. Run the tool to extract strings and rewrite JS files
2. Copy the rewritten JS files back into your modpack's `kubejs/` directory
3. Place `en_us.json` in your resource pack
4. Create `zh_cn.json` (or other locales) by translating the values

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run against sample data
uv run kubejs-strings extract output/kubejs --output test_output
```

## License

MIT
