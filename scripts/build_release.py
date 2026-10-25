#!/usr/bin/env python3
"""Build a checked, deterministic ZIP from the explicit public release inventory."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

from check_release import check_release, collect_release_files, validate_entry


ARCHIVE_PREFIX = "shiyan-shuju"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_release(root: Path, output: Path) -> Path:
    root = Path(root).absolute()
    output = Path(output).absolute()
    if output.suffix.lower() != ".zip":
        raise ValueError("release output must end in .zip")
    if output.is_symlink():
        raise ValueError("release output cannot be a symbolic link")
    issues = check_release(root)
    if issues:
        raise ValueError("Release checks failed:\n" + "\n".join(issues))
    files = collect_release_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".release-", suffix=".zip", dir=output.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
        # STORE avoids compression-library/version differences across platforms.
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in files:
                validate_entry(path, root)
                name = f"{ARCHIVE_PREFIX}/{path.relative_to(root).as_posix()}"
                info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, path.read_bytes())
        os.replace(temporary, output)
        return output
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = build_release(args.root, args.output)
    except (ValueError, OSError) as exc:
        print(f"ERROR {exc}")
        return 1
    print(f"Built {output.name}")
    print(f"SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
