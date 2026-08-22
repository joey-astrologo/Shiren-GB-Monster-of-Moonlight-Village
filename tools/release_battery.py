#!/usr/bin/env python3
"""Run the complete release-candidate validation matrix.

This is intentionally broader than build.sh.  It verifies the normal build, offline
models, hostile string placements, renderer timing/upload delivery, long CPU-health
runs, containment, and the brittle menu/Rankings ownership routes on every layout.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def section(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{bar}\n{title}\n{bar}", flush=True)


def run(*args: str) -> None:
    shown = " ".join(args)
    print(f"\n+ {shown}", flush=True)
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", str(ROOT / "build" / "pycache"))
    subprocess.run(args, cwd=ROOT, check=True, env=env)


def py(tool: str, *args: str) -> None:
    run(PYTHON, f"tools/{tool}", *args)


def main() -> int:
    argparse.ArgumentParser(
        description="Run the complete normal/shuffle/redirect-all release battery."
    ).parse_args()

    section("Fixture privacy, hashes, and generated states")
    py("fixtures.py", "preflight", "--require-states")

    section("Normal build and every save-backed regression")
    run("sh", "build.sh")

    section("Offline translation and model tests")
    run(PYTHON, "-m", "compileall", "-q", "tools")
    py("dialogue_preview.py", "--check")
    py("dialogue_preview.py", "--selftest")
    py("logicdiff.py", "build/_base_expanded.gb", "build/shiren_en.gb")
    py("intro.py", "build/_base_expanded.gb", "--check", "script/intro.tsv")
    py("pool.py", "--selftest")
    py("vwf.py", "--selftest")
    py("name6.py", "--selftest")
    py("rank6.py", "--selftest")
    py("decoyname.py", "--selftest")
    py("nameaudition.py")

    section("Hostile placement ROMs and component controls")
    build_args = ("build/_base_expanded.gb", "script/en.tsv")
    py("build.py", *build_args, "build/shiren_en_shuffle.gb", "--dot-font", "--shuffle")
    py(
        "build.py",
        *build_args,
        "build/shiren_en_redirect_all.gb",
        "--dot-font",
        "--redirect-all",
    )
    py(
        "build.py",
        *build_args,
        "build/orochisymbolspill_native_control.gb",
        "--dot-font",
        "--no-menuvwf",
    )
    py(
        "build.py",
        *build_args,
        "build/rankvwf_control.gb",
        "--dot-font",
        "--no-rankvwf",
    )
    py(
        "build.py",
        *build_args,
        "build/structvwf_control.gb",
        "--dot-font",
        "--no-structvwf",
    )
    py(
        "menuromcensus.py",
        "build/orochisymbolspill_native_control.gb",
        "--ram",
        "saves/shiren_en_menu.srm",
    )

    # Layout-independent: it reads the Japanese control and script/en.tsv, never a
    # placed English ROM, so one run covers all three layouts at once.
    py("healfragmentspill.py", "build/_base_expanded.gb")

    matrix = (
        ("normal", "build/shiren_en.gb"),
        ("shuffle", "build/shiren_en_shuffle.gb"),
        ("redirect-all", "build/shiren_en_redirect_all.gb"),
    )
    for label, rom in matrix:
        section(f"Runtime release matrix: {label}")
        py("titlelogospill.py", rom, "--ram", "saves/shiren_en096_broken_title_screen.srm")
        py("logicdiff.py", "build/_base_expanded.gb", rom)
        py("enemyexp.py", "build/_base_expanded.gb", rom)
        py("introspill.py", "build/_base_expanded.gb", rom)
        py("proptiming.py", rom, "--frames", "3000", "--seeds", "4")
        py("propupload.py", rom, "--frames", "3000", "--seeds", "4")
        py("crashscan.py", rom, "--seeds", "12")
        py("crashscan.py", rom, "--seeds", "12", "--state", "saves/town.state")
        py("boxspill.py", rom, "--seeds", "12", "--frames", "20000")
        py("menuspill.py", rom)
        py("menuspill.py", rom, "--long")
        py("menuspill.py", rom, "--ram", "saves/shiren_en_menu.srm")
        py("menuspill.py", rom, "--help-seals")
        py("menuglyphspill.py", rom)
        py("equipmentmarkerspill.py", rom)
        py("fusioncountspill.py", rom)
        py("playernamedspill.py", rom)
        py("unidentifiednamespill.py", rom)
        py("shopspill.py", rom)
        py("conditionspill.py", rom)
        py("menuromspill.py", rom, "--ram", "saves/shiren_en_menu.srm")
        py("debugmenuspill.py", rom)
        py("mainmenuspill.py", rom)
        py(
            "startspill.py",
            rom,
            "--ram",
            "saves/shiren_en_menu.srm",
            "--wide-ram",
            "saves/shiren_en_ranking_repaired.srm",
        )
        py(
            "rankspill.py",
            rom,
            "--control",
            "build/rankvwf_control.gb",
            "--native-control",
            "build/orochisymbolspill_native_control.gb",
        )
        py(
            "orochisymbolspill.py",
            rom,
            "--native-control",
            "build/orochisymbolspill_native_control.gb",
        )
        py("orochipopupspill.py", rom)
        py(
            "deathrankspill.py",
            rom,
            "--native-control",
            "build/orochisymbolspill_native_control.gb",
        )
        py("rescueexitspill.py", rom)
        py(
            "structspill.py",
            "build/structvwf_control.gb",
            rom,
            "--ram",
            "saves/shiren_en_menu.srm",
            "--rank-ram",
            "saves/shiren_en_ranking_repaired.srm",
        )
        py("savesummaryspill.py", rom)

    section("Release battery complete")
    print("All normal, shuffled, redirect-all, fixture, timing, upload, and containment tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
