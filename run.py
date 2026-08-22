# -*- coding: utf-8 -*-
"""
run.py - Chay TAT CA trong 1 lenh: thu thap du lieu + dung bao cao.

  python run.py            # update (thu thap) + render (dung report.html)
  python run.py --no-fetch # chi dung lai bao cao tu du lieu da co (nhanh)
  python run.py --seen     # dung xong danh dau da xem (mai cho ban CLI, tuy chon)

Sau do:
  - Mo report.html tren may, HOAC
  - Nhan Claude Code "cap nhat bao cao" de minh phan tich lai + dang len dien thoai.
"""
import sys
import runpy
import os

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def _run(module):
    """Chay 1 module nhu script (giu nguyen __main__ cua no)."""
    runpy.run_module(module, run_name="__main__")


def main():
    args = sys.argv[1:]
    if "--no-fetch" not in args:
        print(">>> [1/2] Thu thap du lieu (update.py)...\n")
        _run("update")
        print()
    else:
        print(">>> Bo qua thu thap (--no-fetch)\n")

    print(">>> [2/2] Dung bao cao (render.py)...\n")
    # chuyen tiep co --seen cho render neu co
    sys.argv = ["render.py"] + (["--seen"] if "--seen" in args else [])
    _run("render")

    print("\n>>> XONG. Mo report.html, hoac nhan Claude Code 'cap nhat bao cao'.")


if __name__ == "__main__":
    main()
