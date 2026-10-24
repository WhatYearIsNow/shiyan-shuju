#!/usr/bin/env python3
"""Check the public release inventory, links, and common privacy mistakes.

This is a conservative local check, not a substitute for reviewing source and
image contents. Only files selected by this module can enter a release archive.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT_FILES = frozenset({
    "SKILL.md", "README.md", "LICENSE", "NOTICE.md", "CONTRIBUTING.md",
    "CHANGELOG.md", ".gitignore", ".gitattributes", "pyproject.toml",
})
PUBLIC_DIRECTORIES = {
    ".github": frozenset({".yml", ".yaml", ".md"}),
    "agents": frozenset({".yaml", ".yml", ".md"}),
    "assets": frozenset({".tex", ".svg", ".png"}),
    "docs": frozenset({".md", ".svg", ".png"}),
    "evals": frozenset({".json", ".md"}),
    "examples": frozenset({".py", ".json", ".md", ".tex"}),
    "references": frozenset({".md", ".json"}),
    "scripts": frozenset({".py"}),
    "tests": frozenset({".py", ".json"}),
}
EXCLUDED_NAMES = frozenset({
    ".git", ".local", "build", "dist", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".venv", "venv", "env", "node_modules",
    ".idea", ".vscode", ".DS_Store", "Thumbs.db",
})
REQUIRED_FILES = ("SKILL.md", "README.md", "LICENSE", "NOTICE.md")

# Keep patterns declarative: the scanner also checks its own source and tests.
PRIVATE_PATTERNS = (
    ("absolute local path", re.compile(
        r"(?i)(?<![\w])(?:[a-z]:[\\/]|file:" r"//|/(?:Users|home|mnt|Volumes|tmp|opt|srv|var|etc|root)/)")),
    ("network filesystem path", re.compile(r"\\\\[a-zA-Z0-9_.-]+\\[a-zA-Z0-9_$.-]+\\")),
    ("email address", re.compile(r"(?i)\b[a-z0-9][a-z0-9._%+-]*@[a-z0-9.-]+\.[a-z]{2,}\b")),
    ("possible student ID or personal numeric identifier", re.compile(
        r"(?<![\w.])[1-9][0-9]{7,11}(?![\w.])")),
    ("labelled student ID", re.compile(
        r"(?i)(?:学号|学生编号|student[_ -]?(?:id|number)|bgID)"
        r"[^\n0-9]{0,40}[0-9]{6,18}(?![0-9])")),
)
INLINE_LINK = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|(?:\\.|[^()\s]|\([^()\n]*\))+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)
REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)")


def _is_link(path: Path) -> bool:
    """Also reject Windows junctions/reparse points on supported Python versions."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def validate_entry(path: Path, root: Path) -> None:
    """Refuse links, non-regular files, and paths outside the chosen tree."""
    if _is_link(path):
        raise ValueError(f"{path.relative_to(root).as_posix()}: symbolic links/reparse points are not releasable")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("release entry escapes the project root")
    if not path.is_file():
        raise ValueError(f"{path.relative_to(root).as_posix()}: release entry is not a regular file")


def collect_release_files(root: Path) -> list[Path]:
    """Select an explicit public inventory; private/build trees are never walked.

    Unexpected file types inside public directories fail the check instead of
    quietly disappearing from the release. Unlisted root directories and files
    are outside the package boundary.
    """
    root = Path(root).absolute()
    if not root.is_dir() or _is_link(root):
        raise ValueError("project root must be a real directory")
    result: list[Path] = []
    for name in sorted(ROOT_FILES):
        path = root / name
        if path.exists() or path.is_symlink():
            validate_entry(path, root)
            result.append(path)

    def visit(directory: Path, extensions: frozenset[str]) -> None:
        if _is_link(directory):
            raise ValueError(f"{directory.relative_to(root).as_posix()}: symbolic links/reparse points are not releasable")
        with os.scandir(directory) as entries:
            names = sorted(entries, key=lambda entry: entry.name)
        for entry in names:
            if entry.name in EXCLUDED_NAMES or entry.name.endswith((".pyc", ".pyo")):
                continue
            path = Path(entry.path)
            if _is_link(path):
                raise ValueError(f"{path.relative_to(root).as_posix()}: symbolic links/reparse points are not releasable")
            if path.is_dir():
                visit(path, extensions)
            else:
                validate_entry(path, root)
                if path.suffix.lower() not in extensions:
                    raise ValueError(f"{path.relative_to(root).as_posix()}: file type is outside the public allowlist")
                result.append(path)

    for name, extensions in PUBLIC_DIRECTORIES.items():
        directory = root / name
        if directory.exists() or directory.is_symlink():
            visit(directory, extensions)
    return sorted(result, key=lambda path: path.relative_to(root).as_posix())


def _frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return ["SKILL.md:1: YAML frontmatter must start with ---"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return ["SKILL.md:1: YAML frontmatter has no closing ---"]
    values: dict[str, str] = {}
    issues = []
    active_key = ""
    for number, line in enumerate(lines[1:end], 2):
        if line.startswith((" ", "\t")) and active_key:
            values[active_key] += " " + line.strip()
            continue
        match = re.match(r"([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if not match:
            active_key = ""
            continue
        key, value = match.groups()
        if key in values:
            issues.append(f"SKILL.md:{number}: duplicate frontmatter field {key}")
        values[key] = value.strip().strip("\"'")
        active_key = key
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values.get("name", "")):
        issues.append("SKILL.md: frontmatter name must contain lowercase letters/digits and single hyphens")
    if not values.get("description", "").strip("|>+- "):
        issues.append("SKILL.md: frontmatter description is required")
    return issues


def _markdown_lines(text: str):
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            candidate = marker.group(1)
            if not fence:
                fence = candidate
            elif candidate[0] == fence[0] and len(candidate) >= len(fence):
                fence = ""
            continue
        if not fence and not line.startswith(("    ", "\t")):
            yield number, re.sub(r"(`+).*?\1", "", line)


def _check_links(path: Path, root: Path, text: str, inventory: set[Path]) -> list[str]:
    issues = []
    for number, line in _markdown_lines(text):
        matches = list(INLINE_LINK.finditer(line))
        reference = REFERENCE_LINK.match(line)
        if reference:
            matches.append(reference)
        for match in matches:
            target = match.group(1).strip("<>")
            target = re.sub(r"\\([() ])", r"\1", target)
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            relative = path.relative_to(root).as_posix()
            decoded = unquote(parsed.path)
            candidate = (path.parent / decoded).resolve()
            if decoded.startswith(("/", "\\")) or not candidate.is_relative_to(root.resolve()):
                issues.append(f"{relative}:{number}: relative link escapes the public project")
            elif not candidate.exists():
                issues.append(f"{relative}:{number}: broken relative link")
            elif candidate.is_dir():
                if not any(item.is_relative_to(candidate) for item in inventory):
                    issues.append(f"{relative}:{number}: link targets a directory outside the release")
            elif candidate not in inventory:
                issues.append(f"{relative}:{number}: link targets a file outside the release")
    return issues


def check_release(root: Path, private_values: tuple[str, ...] = ()) -> list[str]:
    root = Path(root).absolute()
    try:
        files = collect_release_files(root)
    except (ValueError, OSError) as exc:
        return [str(exc)]
    issues = [f"{name}: required release file is missing" for name in REQUIRED_FILES
              if not (root / name).is_file()]
    denylist = root / ".local" / "release-denylist.txt"
    if denylist.is_file():
        try:
            private_values += tuple(line.strip() for line in denylist.read_text(encoding="utf-8").splitlines()
                                    if line.strip() and not line.lstrip().startswith("#"))
        except (OSError, UnicodeError):
            issues.append(".local/release-denylist.txt: cannot read UTF-8 private denylist")
    inventory = {path.resolve() for path in files}
    for path in files:
        relative = path.relative_to(root).as_posix()
        private_filename = False
        if any(value and value in relative for value in private_values):
            issues.append("release filename contains a value from the private denylist")
            private_filename = True
        for label, pattern in PRIVATE_PATTERNS:
            if pattern.search(relative):
                issues.append(f"{label} in release filename (path redacted)")
                private_filename = True
        if private_filename:
            continue
        if path.suffix.lower() == ".png":
            continue  # Pixel contents require a separate visual review.
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as exc:
            issues.append(f"{relative}: cannot read UTF-8 text ({type(exc).__name__})")
            continue
        if path.name == "SKILL.md":
            issues.extend(_frontmatter(content))
        for number, line in enumerate(content.splitlines(), 1):
            for label, pattern in PRIVATE_PATTERNS:
                if label == "possible student ID or personal numeric identifier" and path.suffix.lower() == ".py":
                    continue  # Long mathematical constants are valid source inputs.
                if pattern.search(line):
                    # Never echo the matching personal value to a CI log.
                    issues.append(f"{relative}:{number}: {label}; remove or replace with a placeholder")
            if any(value and value in line for value in private_values):
                issues.append(f"{relative}:{number}: contains a value from the private denylist")
        if path.suffix.lower() == ".md":
            issues.extend(_check_links(path, root, content, inventory))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    issues = check_release(args.root)
    if issues:
        for issue in issues:
            print(f"ERROR {issue}")
        return 1
    print(f"Release checks passed ({len(collect_release_files(args.root))} public files).")
    print("Review image contents and data provenance manually before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
