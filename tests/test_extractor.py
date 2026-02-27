"""Tests for the KubeJS String Extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from kubejs_string_extractor.extractor import (
    ExtractedString,
    extract_from_content,
    extract_from_directory,
)
from kubejs_string_extractor.keygen import generate_key, generate_keys
from kubejs_string_extractor.rewriter import rewrite_content
from kubejs_string_extractor.writer import write_lang_json


# ---------------------------------------------------------------------------
# Extractor tests
# ---------------------------------------------------------------------------


class TestDisplayName:
        pass


class TestTextOf:
    def test_basic(self):
        result = extract_from_content(
            "Text.of('Place the pad down in the specified Dimension')", "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "Place the pad down in the specified Dimension"

    def test_with_escaped_quote(self):
        result = extract_from_content(
            "Text.of(\"It\\'s less... talkative now\")", "test.js"
        )
        assert len(result.strings) == 1


class TestTextColor:
    def test_red(self):
        result = extract_from_content(
            "Text.red('Increased Energy Consumption!')", "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "Increased Energy Consumption!"
        assert result.strings[0].pattern_type == "Text.color"

    def test_green(self):
        result = extract_from_content(
            "Text.green('Increased Energy Capacity')", "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "Increased Energy Capacity"

    def test_yellow(self):
        result = extract_from_content(
            "Text.yellow('All The Mods Announcements')", "test.js"
        )
        assert len(result.strings) == 1


class TestSceneText:
    def test_basic(self):
        result = extract_from_content(
            "scene.text(80, 'The Edges Must Be Casings', [0, 4.5, 4.5])", "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "The Edges Must Be Casings"
        assert result.strings[0].pattern_type == "scene.text"


class TestAnnouncement:
    def test_basic(self):
        result = extract_from_content(
            'addAnnouncement("4.0", "Added mods: Ars Creo, Ice and Fire, Oritech,")', "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "Added mods: Ars Creo, Ice and Fire, Oritech,"
        assert result.strings[0].pattern_type == "announcement"


class TestAppend:
    def test_basic(self):
        result = extract_from_content(
            '.append(" for public beta testing!")', "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == " for public beta testing!"


class TestStatusMessage:
    def test_assign(self):
        result = extract_from_content(
            'player.statusMessage = "Dragon or Dragon Roost not found nearby..."', "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "Dragon or Dragon Roost not found nearby..."

    def test_set_method(self):
        result = extract_from_content(
            'event.player.setStatusMessage(Text.red("This server does not allow you to use this item!"))',
            "test.js",
        )
        # Matches both Text.color and setStatusMessage patterns
        assert len(result.strings) == 2
        values = [s.value for s in result.strings]
        assert "This server does not allow you to use this item!" in values


class TestTell:
    def test_direct_string(self):
        result = extract_from_content(
            'event.server.tell("Starting server frozen...")', "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "Starting server frozen..."

    def test_text_red(self):
        result = extract_from_content(
            "event.server.tell(Text.red('Hyperboxes will be removed on version 6.0+'))",
            "test.js",
        )
        values = [s.value for s in result.strings]
        assert "Hyperboxes will be removed on version 6.0+" in values


class TestTranslatable:
    def test_extracts_keys(self):
        result = extract_from_content(
            'Text.translate("announcements.atm.dismiss_up_to_version", Text.blue(currentVersion.toString()))',
            "test.js",
        )
        assert "announcements.atm.dismiss_up_to_version" in result.translatable_keys


class TestFiltering:
    def test_skips_item_ids(self):
        result = extract_from_content(
            "Text.of('minecraft:oak_sign')", "test.js"
        )
        assert len(result.strings) == 0

    def test_skips_formatting_only(self):
        result = extract_from_content(
            "Text.of('§0███§7███§0███')", "test.js"
        )
        assert len(result.strings) == 0

    def test_skips_comments(self):
        result = extract_from_content(
            "// Text.of('This is a comment')", "test.js"
        )
        assert len(result.strings) == 0

    def test_keeps_real_strings(self):
        result = extract_from_content(
            "Text.of('§7Needs at least Netherite to be mined')", "test.js"
        )
        assert len(result.strings) == 1
        assert result.strings[0].value == "§7Needs at least Netherite to be mined"


# ---------------------------------------------------------------------------
# Keygen tests
# ---------------------------------------------------------------------------


class TestKeygen:
    def test_key_format(self):
        s = ExtractedString(
            value="Test",
            source_file="C:/modpack/kubejs/startup_scripts/Applied Energistics/Universal_Press.js",
            line_number=8,
            pattern_type="displayName",
        )
        key = generate_key(s, 1, "kubejs")
        assert key == "kubejs.startup.universal_press.1"

    def test_generate_keys_dedup(self):
        strings = [
            ExtractedString("Hello", "kubejs/client_scripts/test.js", 1, "Text.of"),
            ExtractedString("Hello", "kubejs/client_scripts/test.js", 5, "Text.of"),
            ExtractedString("World", "kubejs/client_scripts/test.js", 10, "Text.of"),
        ]
        result = generate_keys(strings, "kubejs")
        assert len(result) == 2
        assert "kubejs.client.test.1" in result
        assert "kubejs.client.test.2" in result
        assert result["kubejs.client.test.1"] == "Hello"
        assert result["kubejs.client.test.2"] == "World"


# ---------------------------------------------------------------------------
# Writer tests
# ---------------------------------------------------------------------------


class TestWriter:
    def test_write_lang_json(self, tmp_path: Path):
        translations = {
            "kubejs.test.1": "Hello World",
            "kubejs.test.2": "Goodbye World",
        }
        output_file = write_lang_json(translations, tmp_path, "test_pack")

        assert output_file.exists()
        assert "test_pack" in str(output_file)
        assert output_file.name == "en_us.json"

        import json
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["kubejs.test.1"] == "Hello World"
        assert data["kubejs.test.2"] == "Goodbye World"


# ---------------------------------------------------------------------------
# Rewriter tests
# ---------------------------------------------------------------------------


class TestRewriter:
    def test_rewrite_display_name(self):
        pass


    def test_rewrite_text_of(self):
        code = "Text.of('Place the pad down in the specified Dimension')"
        mapping = {"Place the pad down in the specified Dimension": "kubejs.client.tooltips.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert result == "Text.translate('kubejs.client.tooltips.1')"

    def test_rewrite_text_red(self):
        code = "Text.red('Increased Energy Consumption!')"
        mapping = {"Increased Energy Consumption!": "kubejs.client.mek.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert result == "Text.translate('kubejs.client.mek.1').red()"

    def test_rewrite_text_green(self):
        code = "Text.green('Increased Energy Capacity')"
        mapping = {"Increased Energy Capacity": "kubejs.client.mek.2"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert result == "Text.translate('kubejs.client.mek.2').green()"

    def test_rewrite_scene_text(self):
        code = "scene.text(80, 'The Edges Must Be Casings', [0, 4.5, 4.5]).placeNearTarget();"
        mapping = {"The Edges Must Be Casings": "kubejs.client.fission.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert "scene.text(80, Text.translate('kubejs.client.fission.1')" in result

    def test_rewrite_announcement(self):
        code = 'addAnnouncement("4.0", "Added mods: Ars Creo, Ice and Fire")'
        mapping = {"Added mods: Ars Creo, Ice and Fire": "kubejs.server.ann.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert "Text.translate('kubejs.server.ann.1')" in result
        assert '"4.0"' in result  # version preserved

    def test_rewrite_append(self):
        code = '.append(" for public beta testing!")'
        mapping = {" for public beta testing!": "kubejs.server.ann.2"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert ".append(Text.translate('kubejs.server.ann.2'))" in result

    def test_rewrite_status_message(self):
        code = 'player.statusMessage = "Dragon or Dragon Roost not found nearby..."'
        mapping = {"Dragon or Dragon Roost not found nearby...": "kubejs.startup.custom.14"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert ".statusMessage = Text.translate('kubejs.startup.custom.14')" in result

    def test_rewrite_tell_direct(self):
        code = 'event.server.tell("Starting server frozen...")'
        mapping = {"Starting server frozen...": "kubejs.server.freeze.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert ".tell(Text.translate('kubejs.server.freeze.1'))" in result

    def test_rewrite_tell_text_color(self):
        """For .tell(Text.red('...')), the inner Text.red() gets rewritten."""
        code = "event.server.tell(Text.red('Hyperboxes will be removed on version 6.0+'))"
        mapping = {"Hyperboxes will be removed on version 6.0+": "kubejs.server.hyper.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 1
        assert "Text.translate('kubejs.server.hyper.1').red()" in result

    def test_skips_comments(self):
        code = "// Text.of('This should not be changed')"
        mapping = {"This should not be changed": "kubejs.test.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 0
        assert result == code

    def test_skips_unmapped_strings(self):
        code = "Text.of('Not in mapping')"
        mapping = {"Something else": "kubejs.test.1"}
        result, count = rewrite_content(code, mapping)
        assert count == 0
        assert result == code

    def test_multiple_replacements_per_line(self):
        code = "    Text.red('Energy!'),\n    Text.green('Capacity!')\n"
        mapping = {"Energy!": "k.1", "Capacity!": "k.2"}
        result, count = rewrite_content(code, mapping)
        assert count == 2
        assert "Text.translate('k.1').red()" in result
        assert "Text.translate('k.2').green()" in result


# ---------------------------------------------------------------------------
# Integration test with sample data
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests that run against the sample output/ data if available."""

    @pytest.fixture
    def sample_kubejs_dir(self) -> Path | None:
        """Return path to sample kubejs dir, or skip if not available."""
        candidate = Path(__file__).parent.parent / "output" / "kubejs"
        if not candidate.exists():
            pytest.skip("Sample output/kubejs directory not found")
        return candidate

    def test_extracts_known_strings(self, sample_kubejs_dir: Path):
        result = extract_from_directory(sample_kubejs_dir)
        values = [s.value for s in result.strings]

        # From Universal_Press.js
        assert "Inscriber Universal Press" in values

        # From tooltips.js
        assert "Place the pad down in the specified Dimension" in values
        assert "Sneak Right Click with both hands empty to teleport" in values

        # From Mekanism-Tooltips.js
        assert "Increased Energy Consumption!" in values
        assert "Increased Energy Capacity" in values

        # From CustomAdditions.js (§b prefix is kept as-is)
        assert "§bMagical Soil" in values
        assert "Liquid Souls" in values

        # From ponder
        assert "The Edges Must Be Casings" in values

    def test_extracts_translatable_keys(self, sample_kubejs_dir: Path):
        result = extract_from_directory(sample_kubejs_dir)
        assert "announcements.atm.dismiss_up_to_version" in result.translatable_keys
        assert "kubejs.atm.click_here" in result.translatable_keys

    def test_produces_nonempty_output(self, sample_kubejs_dir: Path, tmp_path: Path):
        result = extract_from_directory(sample_kubejs_dir)
        translations = generate_keys(result.strings, "kubejs")
        assert len(translations) > 50  # We expect many strings from ATM10

        output_file = write_lang_json(translations, tmp_path)
        assert output_file.exists()
        assert output_file.stat().st_size > 100

    def test_rewrite_produces_modified_files(self, sample_kubejs_dir: Path, tmp_path: Path):
        """Full pipeline: extract → keygen → rewrite, verify output files contain translatable()."""
        result = extract_from_directory(sample_kubejs_dir)
        translations = generate_keys(result.strings, "kubejs")
        value_to_key = {v: k for k, v in translations.items()}

        from kubejs_string_extractor.rewriter import rewrite_directory
        rewrite_results = rewrite_directory(sample_kubejs_dir, value_to_key, tmp_path)

        assert len(rewrite_results) > 5  # multiple files should be rewritten

        # Check that at least one output file contains Text.translate
        has_translatable = False
        for r in rewrite_results:
            if "Text.translate(" in r.modified_content:
                has_translatable = True
                break
        assert has_translatable, "No rewritten file contains Text.translate()"
