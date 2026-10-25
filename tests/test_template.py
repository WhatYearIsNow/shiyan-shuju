import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('check_template', ROOT / 'scripts/check_template.py')
QA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QA)


class TemplateTests(unittest.TestCase):
    def test_missing_tool_fails_before_writing_artifacts(self):
        scratch = ROOT / 'build/template-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='missing-tool-', dir=scratch) as directory:
            self.assertTrue(Path(directory).resolve().is_relative_to(scratch.resolve()))
            output = Path(directory) / 'not-created'
            with patch.object(QA.shutil, 'which', return_value=None):
                with self.assertRaisesRegex(ValueError, 'Missing xelatex'):
                    QA.check(output, render=True)
            self.assertFalse(output.exists())

    @unittest.skipUnless(
        os.environ.get('SHIYAN_TEMPLATE_INTEGRATION') == '1',
        'Set SHIYAN_TEMPLATE_INTEGRATION=1 with XeLaTeX and pdftoppm installed',
    )
    def test_compile_and_render_all_fixtures(self):
        scratch = ROOT / 'build/template-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='layout-', dir=scratch) as directory:
            self.assertTrue(Path(directory).resolve().is_relative_to(scratch.resolve()))
            results = QA.check(directory, render=True)
            self.assertEqual(len(results), 3)
            for result in results:
                self.assertTrue(result['compiled'])
                self.assertTrue(result['rendered_pages'])


if __name__ == '__main__':
    unittest.main()
