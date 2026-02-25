"""CLI entry point for kubejs-string-extractor."""

from __future__ import annotations

from pathlib import Path

import click

from kubejs_string_extractor.extractor import extract_from_directory
from kubejs_string_extractor.keygen import generate_keys
from kubejs_string_extractor.rewriter import rewrite_directory
from kubejs_string_extractor.writer import write_lang_json


@click.group()
@click.version_option()
def main() -> None:
    """KubeJS String Extractor - Extract translatable strings from KubeJS scripts."""


@main.command()
@click.argument("kubejs_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=Path("extracted"),
    show_default=True,
    help="Output directory for the resource pack lang files and modified scripts.",
)
@click.option(
    "--namespace", "-n",
    default="kubejs",
    show_default=True,
    help="Translation key namespace prefix.",
)
@click.option(
    "--pack-namespace",
    default="kubejs_string_extractor",
    show_default=True,
    help="Resource pack namespace for output directory structure.",
)
@click.option(
    "--rewrite/--no-rewrite",
    default=True,
    show_default=True,
    help="Rewrite original JS files to use Text.translatable() calls.",
)
@click.option(
    "--in-place",
    is_flag=True,
    default=False,
    help="Modify JS files in place instead of writing to the output directory.",
)
def extract(
    kubejs_dir: Path,
    output: Path,
    namespace: str,
    pack_namespace: str,
    rewrite: bool,
    in_place: bool,
) -> None:
    """Extract translatable strings from a KubeJS directory.

    KUBEJS_DIR is the path to the modpack's kubejs/ directory containing
    client_scripts/, server_scripts/, and/or startup_scripts/.

    By default, this will:
    1. Extract all hardcoded strings from JS files
    2. Generate translation keys and write en_us.json
    3. Rewrite the JS files to use Text.translatable() calls
    """
    click.echo(f"📂 Scanning KubeJS directory: {kubejs_dir}")

    # Step 1: Extract strings
    result = extract_from_directory(kubejs_dir)

    if not result.strings:
        click.echo("⚠️  No translatable strings found.")
        return

    click.echo(f"✅ Found {len(result.strings)} translatable strings")

    # Step 2: Generate translation keys
    translations = generate_keys(result.strings, namespace)
    click.echo(f"🔑 Generated {len(translations)} unique translation keys")

    # Step 3: Write lang JSON
    lang_file = write_lang_json(translations, output, pack_namespace)
    click.echo(f"📄 Wrote lang file: {lang_file}")

    # Step 4: Rewrite JS files
    if rewrite:
        # Build reverse mapping: string_value -> key
        value_to_key = {v: k for k, v in translations.items()}

        if in_place:
            click.echo("✏️  Rewriting JS files in place...")
            rewrite_results = rewrite_directory(kubejs_dir, value_to_key)
        else:
            scripts_output = output / "kubejs"
            click.echo(f"✏️  Writing modified JS files to: {scripts_output}")
            rewrite_results = rewrite_directory(kubejs_dir, value_to_key, scripts_output)

        total_replacements = sum(r.replacements_made for r in rewrite_results)
        click.echo(
            f"📝 Rewrote {len(rewrite_results)} files "
            f"({total_replacements} lines modified)"
        )

    click.echo("🎉 Done!")


if __name__ == "__main__":
    main()
