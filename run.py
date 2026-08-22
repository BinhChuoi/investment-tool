# -*- coding: utf-8 -*-
"""
run.py - Do everything in one command: collect data + build report.

  python run.py            # update (collect) + render (build report.html)
  python run.py --no-fetch # only rebuild the report from existing data (fast)
  python run.py --seen     # after building, mark everything as seen (weekly)

Then:
  - Open report.html locally, OR
  - Ask Claude Code "cap nhat bao cao" to re-analyze + publish to phone.
"""
import sys
import runpy
import os

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def _run(module):
    """Run a module as a script (preserving its __main__)."""
    runpy.run_module(module, run_name="__main__")


def main():
    args = sys.argv[1:]
    if "--no-fetch" not in args:
        print(">>> [1/2] Collecting data (update.py)...\n")
        _run("update")
        print()
    else:
        print(">>> Skipping collection (--no-fetch)\n")

    print(">>> [2/2] Building report (render.py)...\n")
    # forward --seen to render if present
    sys.argv = ["render.py"] + (["--seen"] if "--seen" in args else [])
    _run("render")

    print("\n>>> DONE. Open report.html, or ask Claude Code 'cap nhat bao cao'.")


if __name__ == "__main__":
    main()
