import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('verification', ROOT / 'scripts/verify.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VerificationTests(unittest.TestCase):
    def temporary(self):
        parent = ROOT / 'build'
        parent.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='verification-', dir=parent)
        self.assertTrue(Path(temporary.name).resolve().is_relative_to(parent.resolve()))
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_launch_failure_replaces_stale_success_and_stops(self):
        output = self.temporary()
        (output / 'report.json').write_text('{"status":"passed"}')
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            self.assertEqual(json.loads((output / 'report.json').read_text())['status'], 'running')
            raise FileNotFoundError('constructed missing executable')

        report = MODULE.verify(output=output, package=True, runner=run)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['stages'][0]['exit_code'], 2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads((output / 'report.json').read_text())['status'], 'failed')

    def test_timeout_is_a_recorded_failure_without_packaging(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])

        report = MODULE.verify(output=self.temporary(), package=True, runner=run)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['stages'][0]['exit_code'], 124)
        self.assertEqual(len(calls), 1)

    def test_failure_stops_before_release_and_packaging(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=1 if len(calls) == 2 else 0,
                                   stdout='', stderr='constructed failure' if len(calls) == 2 else 'Ran 23 tests\nOK')

        output = self.temporary()
        report = MODULE.verify(output=output, package=True, runner=run)
        self.assertEqual(len(calls), 2)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(json.loads((output / 'report.json').read_text())['status'], 'failed')
        self.assertIn('constructed failure', (output / 'tests.log').read_text())

    def test_package_runs_last_and_skip_evidence_is_retained(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs['env']))
            return SimpleNamespace(returncode=0, stdout='', stderr='Ran 4 tests\nOK (skipped=1)')

        report = MODULE.verify(output=self.temporary(), template=True, package=True, runner=run)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual([s['name'] for s in report['stages']],
                         ['compatibility', 'tests', 'release-check', 'package'])
        self.assertIn('scripts/build_release.py', calls[-1][0])
        self.assertTrue(all(env['SHIYAN_TEMPLATE_INTEGRATION'] == '1' for _, env in calls))
        self.assertEqual(report['stages'][0]['skipped'], 1)
