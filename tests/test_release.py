"""Release tests use temporary, synthetic repositories; no course data is read."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_release as builder
import check_release as checker


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        fixture_parent = Path(__file__).resolve().parents[1] / "build"
        fixture_parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="release-tests-", dir=fixture_parent)
        self.assertTrue(
            Path(self.temporary.name).resolve().is_relative_to(fixture_parent.resolve())
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "fixture"
        self.root.mkdir()
        self.write(
            "SKILL.md",
            "---\nname: demo-skill\ndescription: Constructed test skill\n---\n\n# Demo\n",
        )
        self.write("README.md", "# Demo\n\n[Skill](SKILL.md)\n")
        self.write("LICENSE", "MIT License\n\nConstructed fixture.\n")
        self.write("NOTICE.md", "# Fixture\n\nAll data is constructed.\n")

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def test_minimal_public_release_passes(self):
        self.assertEqual(checker.check_release(self.root), [])

    def test_missing_required_file_fails(self):
        (self.root / "LICENSE").unlink()
        self.assertTrue(any("LICENSE" in issue for issue in checker.check_release(self.root)))

    def test_frontmatter_missing_and_invalid_fields_fail(self):
        cases = (
            "# no frontmatter\n",
            "---\nname: valid\ndescription: missing close\n",
            "---\nname: UPPER_case\ndescription: test\n---\n",
            "---\nname: valid\n---\n",
            "---\nname: valid\nname: second\ndescription: test\n---\n",
        )
        for content in cases:
            with self.subTest(content=content):
                self.write("SKILL.md", content)
                self.assertTrue(checker.check_release(self.root))

    def test_multiline_description_passes(self):
        self.write(
            "SKILL.md",
            "---\nname: demo-skill\ndescription: >\n  Synthetic multiline\n  description.\n---\n",
        )
        self.assertEqual(checker.check_release(self.root), [])

    def test_inline_reference_encoded_and_image_links_pass(self):
        self.write("docs/有 空格.md", "# Target\n")
        self.write("docs/a(b).md", "# Parenthesis\n")
        # A PNG placeholder is sufficient: link validation does not decode images.
        (self.root / "docs" / "diagram.png").write_bytes(b"synthetic pixel fixture")
        self.write(
            "README.md",
            "[A](<docs/有 空格.md>)\n[B](docs/有%20空格.md#target)\n"
            "[C](docs/a(b).md)\n![Image](docs/diagram.png)\n[D][ref]\n"
            "[ref]: docs/有%20空格.md \"Title\"\n[anchor](#demo)\n"
            "[external](https://example.invalid/readme)\n",
        )
        self.assertEqual(checker.check_release(self.root), [])

    def test_fenced_and_inline_code_links_are_not_real_links(self):
        self.write(
            "README.md",
            "# Demo\n\n```markdown\n[x](missing.md)\n```\n"
            "`[inline](missing.md)`\n\n    [indented](missing.md)\n",
        )
        self.assertEqual(checker.check_release(self.root), [])

    def test_broken_relative_link_fails(self):
        self.write("README.md", "[broken](missing.md)\n")
        self.assertTrue(
            any("broken relative link" in issue for issue in checker.check_release(self.root))
        )

    def test_link_cannot_escape_or_target_unreleased_material(self):
        self.write(".local/private.md", "synthetic private material\n")
        self.write("README.md", "[outside](../outside.md)\n[private](.local/private.md)\n")
        issues = checker.check_release(self.root)
        self.assertTrue(any("escapes" in issue for issue in issues))
        self.assertTrue(any("outside the release" in issue for issue in issues))

    def test_directory_links_must_have_public_contents(self):
        self.write("references/guide.md", "# Guide\n")
        self.write(".local/private.md", "synthetic private material\n")
        self.write("README.md", "[good](references/)\n[bad](.local/)\n")
        issues = checker.check_release(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("directory outside the release", issues[0])

    def test_private_content_patterns_fail_without_echoing_values(self):
        values = (
            "Q" + ":/personal/data",
            "/" + "home/person/data",
            "file:" + "///personal/data",
            "\\" * 2 + "server\\share\\secret",
            "synthetic" + "@" + "example.invalid",
            "41" * 5,
        )
        for value in values:
            with self.subTest(kind=value[:1]):
                self.write("README.md", "# Fixture\n\n" + value + "\n")
                issues = checker.check_release(self.root)
                self.assertTrue(issues)
                self.assertTrue(all(value not in issue for issue in issues))

    def test_scanner_does_not_flag_its_regex_source(self):
        self.write("scripts/check_release.py", Path(checker.__file__).read_text(encoding="utf-8"))
        self.write("tests/test_release.py", Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual(checker.check_release(self.root), [])

    def test_calculation_numbers_are_allowed_but_labelled_ids_are_not(self):
        synthetic_number = "10" * 5
        self.write("scripts/math.py", f'value = "{synthetic_number}"\n')
        self.assertEqual(checker.check_release(self.root), [])
        self.write("scripts/math.py", 'student_id = "' + synthetic_number + '"\n')
        self.assertTrue(
            any("labelled student ID" in issue for issue in checker.check_release(self.root))
        )

    def test_local_denylist_catches_known_private_value_without_packaging_it(self):
        private_value = "42" * 5
        self.write("scripts/math.py", 'value = "' + private_value + '"\n')
        self.write(".local/release-denylist.txt", "# Local only\n" + private_value + "\n")
        issues = checker.check_release(self.root)
        self.assertTrue(any("private denylist" in issue for issue in issues))
        self.assertTrue(all(private_value not in issue for issue in issues))
        self.assertFalse(
            any(".local" in path.parts for path in checker.collect_release_files(self.root))
        )

    def test_private_build_cache_and_unknown_roots_never_enter_archive(self):
        self.write("scripts/public.py", "print('synthetic')\n")
        for relative in (
            ".local/private.md",
            ".git/config",
            "build/old.zip",
            "scripts/__pycache__/old.pyc",
            "scripts/.local/private.py",
            "scripts/venv/secret.py",
            "unlisted/private.md",
            "secrets.txt",
        ):
            self.write(relative, "synthetic excluded file\n")
        output = builder.build_release(self.root, self.root / "build" / "release.zip")
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(names), 5)
        self.assertIn("shiyan-shuju/scripts/public.py", names)
        self.assertFalse(any("private" in name or "cache" in name for name in names))

    def test_unexpected_file_inside_public_directory_fails(self):
        self.write("assets/raw.pdf", "unapproved input\n")
        self.assertTrue(any("allowlist" in issue for issue in checker.check_release(self.root)))

    def test_non_utf8_public_text_fails(self):
        (self.root / "README.md").write_bytes(b"\xff\xfe")
        self.assertTrue(any("UTF-8" in issue for issue in checker.check_release(self.root)))

    def test_build_is_byte_identical_after_source_timestamp_change(self):
        first = builder.build_release(self.root, self.root / "build" / "first.zip").read_bytes()
        for path in checker.collect_release_files(self.root):
            os.utime(path, (60, 60))
        output = builder.build_release(self.root, self.root / "build" / "second.zip")
        self.assertEqual(first, output.read_bytes())
        with zipfile.ZipFile(output) as archive:
            for info in archive.infolist():
                self.assertEqual(info.date_time, builder.ZIP_TIMESTAMP)
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.external_attr >> 16, 0o100644)
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertTrue(info.filename.startswith("shiyan-shuju/"))
                self.assertNotIn("\\", info.filename)

    def test_failed_build_does_not_overwrite_existing_output(self):
        output = self.root / "build" / "release.zip"
        output.parent.mkdir()
        output.write_bytes(b"previous valid artifact")
        self.write("README.md", "[missing](no-file.md)\n")
        with self.assertRaises(ValueError):
            builder.build_release(self.root, output)
        self.assertEqual(output.read_bytes(), b"previous valid artifact")

    def test_symlink_file_and_directory_are_rejected(self):
        target = self.write("docs/target.md", "# Target\n")
        link = self.root / "docs" / "alias.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links require permission on this platform")
        self.assertTrue(
            any("symbolic links" in issue for issue in checker.check_release(self.root))
        )
        link.unlink()
        directory_link = self.root / "references"
        directory_link.symlink_to(target.parent, target_is_directory=True)
        self.assertTrue(
            any("symbolic links" in issue for issue in checker.check_release(self.root))
        )

    def test_reparse_flag_and_link_rejection_without_os_privilege(self):
        flags = SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400)
        with mock.patch.object(Path, "lstat", return_value=flags):
            self.assertTrue(checker._is_link(Path("synthetic")))
        target = self.write("scripts/linked.py", "# Synthetic\n")
        real_is_link = checker._is_link
        with mock.patch.object(
            checker, "_is_link", side_effect=lambda path: path == target or real_is_link(path)
        ):
            self.assertTrue(
                any("symbolic links" in issue for issue in checker.check_release(self.root))
            )
            with self.assertRaises(ValueError):
                builder.build_release(self.root, self.root / "build" / "linked.zip")

    def test_output_extension_and_cli_failure_status(self):
        with self.assertRaises(ValueError):
            builder.build_release(self.root, self.root / "build" / "release.txt")
        self.write("README.md", "[missing](no-file.md)\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(["--root", str(self.root)]), 1)
            self.assertEqual(
                builder.main(
                    ["--root", str(self.root), "--output", str(self.root / "build" / "bad.zip")]
                ),
                1,
            )


if __name__ == "__main__":
    unittest.main()
