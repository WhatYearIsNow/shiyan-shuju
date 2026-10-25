#!/usr/bin/env python3
"""Compile three synthetic layout fixtures; optionally render every page.

Requires XeLaTeX; --render additionally requires pdftoppm. Artifacts stay in
the requested output directory and are never included in a release archive.
"""

from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def fixture_bodies():
    short = r"""\noindent\textbf{合成示例——实验数据处理}
\section{测量结果}
数据仅用于检验版式，不是实际实验记录。
\begin{equation*}x=(10.020\pm0.023)\,\mathrm{mm}.\end{equation*}
"""
    wide = r"""\noindent\textbf{合成示例——宽表与公式}
\section{测量表}
\begin{center}\resizebox{\linewidth}{!}{%
\begin{tabular}{ccccccccc}\toprule
序号 & $x_1$ & $x_2$ & $x_3$ & $x_4$ & $x_5$ & $x_6$ & $x_7$ & 单位\\
\midrule
1 & 1.00 & 2.00 & 3.00 & 4.00 & 5.00 & 6.00 & 7.00 & mm\\
2 & 1.01 & 2.01 & 3.01 & 4.01 & 5.01 & 6.01 & 7.01 & mm\\
\bottomrule\end{tabular}}\end{center}
\bgsub{计算说明}
\begin{equation*}\begin{aligned}
u_c^2&=\left(\frac{\partial f}{\partial x_1}u_1\right)^2
      +\left(\frac{\partial f}{\partial x_2}u_2\right)^2\\
     &\quad+\left(\frac{\partial f}{\partial x_3}u_3\right)^2.
\end{aligned}\end{equation*}
表格与公式是合成排版样例；实际处理须先确认独立性假设。
"""
    sections = []
    for i in range(18):
        sections.append(r'\section{合成分组 ' + str(i + 1) + '}\n')
        sections.append(
            (
                '此段仅作分页测试。原始读数、单位、口径和计算结果应能追溯。'
                '内容区与框线保留间距，页眉重复，右下签字区不被正文覆盖。\n\n'
            )
            * 3
        )
        sections.append(r'\begin{equation*}y=a+bx,\quad U=ku_c.\end{equation*}' + '\n')
    return {'short': short, 'wide': wide, 'multipage': ''.join(sections)}


def check(output, render=False):
    engine = shutil.which('xelatex')
    renderer = shutil.which('pdftoppm') if render else None
    if not engine or (render and not renderer):
        raise ValueError('Missing xelatex or requested pdftoppm renderer')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    template = (ROOT / 'assets/report-landscape.tex').read_text(encoding='utf-8')
    if template.count('%%% BEGIN BODY %%%') != 1 or template.count('%%% END BODY %%%') != 1:
        raise ValueError('Template body markers are missing or duplicated')
    results = []
    for name, body in fixture_bodies().items():
        tex = output / (name + '.tex')
        tex.write_text(
            template.replace('%%% BEGIN BODY %%%', '%%% BEGIN BODY %%%\n' + body), encoding='utf-8'
        )
        # Two passes resolve page references and report the final warnings.
        for _ in range(2):
            completed = subprocess.run(
                [
                    engine,
                    '-no-shell-escape',
                    '-halt-on-error',
                    '-interaction=nonstopmode',
                    '-output-directory',
                    str(output),
                    str(tex),
                ],
                capture_output=True,
                timeout=120,
            )
            if completed.returncode:
                raise ValueError(f'{name}: XeLaTeX failed; see its log')
        log = tex.with_suffix('.log').read_text(encoding='utf-8', errors='replace')
        problems = [
            term
            for term in (
                'Overfull',
                'Missing character:',
                'LaTeX Error:',
                'Undefined control sequence',
                'headheight is too small',
            )
            if term in log
        ]
        if problems:
            raise ValueError(f'{name}: layout/compile warnings: {problems}')
        images = []
        if render:
            # Remove only this fixture's numbered renders; old pages must not
            # make a newly shortened/failed multipage render appear complete.
            for old_image in output.glob(name + '-*.png'):
                if re.fullmatch(re.escape(name) + r'-\d+\.png', old_image.name):
                    old_image.unlink()
            completed = subprocess.run(
                [renderer, '-r', '100', '-png', str(tex.with_suffix('.pdf')), str(output / name)],
                capture_output=True,
                timeout=120,
            )
            if completed.returncode:
                raise ValueError(f'{name}: rendering failed')
            images = sorted(p.name for p in output.glob(name + '-*.png'))
            if not images:
                raise ValueError(f'{name}: no rendered pages')
            if name == 'multipage' and len(images) < 2:
                raise ValueError('Multipage fixture did not exercise a page break')
        results.append(
            {
                'case': name,
                'compiled': True,
                'log_checks_passed': True,
                'rendered_pages': images,
                'visual_review': 'pending',
            }
        )
    (output / 'qa.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/template-qa')
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.output, args.render), indent=2))
    except (ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
