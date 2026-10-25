#!/usr/bin/env python3
"""Run ordered validation gates and save evidence; stop at the first failure."""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT, output=None, template=False, package=False, runner=None):
    root = Path(root).resolve()
    output = Path(output or root / 'build/verification').resolve()
    output.mkdir(parents=True, exist_ok=True)
    runner = runner or subprocess.run
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    # Make the selected mode independent of a caller's previous shell setting.
    env['SHIYAN_TEMPLATE_INTEGRATION'] = '1' if template else '0'
    stages = [
        (
            'compatibility',
            ['-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_uncertainty.py', '-v'],
        ),
        ('tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('release-check', ['scripts/check_release.py']),
    ]
    if package:
        stages.append(
            ('package', ['scripts/build_release.py', '--output', 'build/shiyan-shuju.zip'])
        )
    report = {
        'python': platform.python_version(),
        'platform': platform.system(),
        'template_integration': template,
        'status': 'running',
        'stages': [],
    }
    # Invalidate any earlier successful run before starting subprocesses.
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, arguments in stages:
        command = [sys.executable, '-B', *arguments]
        try:
            result = runner(
                command,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600,
            )
            exit_code = result.returncode
            log = result.stdout + result.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            exit_code = 124 if isinstance(exc, subprocess.TimeoutExpired) else 2
            log = f'{type(exc).__name__}: {exc}\n'
        (output / (name + '.log')).write_text(log, encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?', log)
        skipped = re.search(r'skipped=(\d+)', log)
        report['stages'].append(
            {
                'name': name,
                'command': arguments,
                'exit_code': exit_code,
                'tests_run': int(count[1]) if count else None,
                'skipped': int(skipped[1]) if skipped else 0,
                'log': name + '.log',
            }
        )
        report['status'] = 'failed' if exit_code else 'running'
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if exit_code:
            return report
    report['status'] = 'passed'
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--template', action='store_true', help='Require real TeX/render integration'
    )
    parser.add_argument(
        '--package', action='store_true', help='Build ZIP only after all gates pass'
    )
    parser.add_argument('--output', type=Path, default=None, help='Evidence directory')
    args = parser.parse_args()
    report = verify(output=args.output, template=args.template, package=args.package)
    print(json.dumps(report, indent=2))
    if report['status'] == 'failed':
        directory = Path(args.output or ROOT / 'build/verification')
        print(
            (directory / report['stages'][-1]['log']).read_text(encoding='utf-8'), file=sys.stderr
        )
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
