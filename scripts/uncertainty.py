#!/usr/bin/env python3
"""Backward-compatible API facade and command-line entry point."""
import sys
from decimal import DecimalException
from labmath import *  # Compatibility with existing experiment drivers.
from labmath.cli import main

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        sys.exit(main())
    except (ValueError, DecimalException, ZeroDivisionError) as exc:
        print(f"输入或计算错误：{exc}", file=sys.stderr)
        sys.exit(2)
