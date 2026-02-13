"""GHEval build script — creates an executable via PyInstaller.

Usage:
    python build.py              # onefile (default)
    python build.py --onedir     # onedir
"""

import subprocess
import shutil
import sys
import os
import time

SPEC_FILE = "gheval.spec"
DIST_DIR = "dist"
BUILD_DIR = "build"


def run(cmd, desc, show_output=False, env=None):
    """Run a command, streaming output in real time if show_output is True."""
    print(f"  [{desc}]")
    if show_output:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if any(k in line for k in ("INFO: Building", "INFO: Appending",
                                        "INFO: checking", "INFO: Looking",
                                        "INFO: Processing", "WARNING",
                                        "INFO: Build complete",
                                        "INFO: Copying bootloader")):
                print(f"    {line.split(' INFO: ')[-1] if ' INFO: ' in line else line}")
        proc.wait()
        if proc.returncode != 0:
            print(f"  [ERROR] {desc} failed (exit code {proc.returncode})")
            sys.exit(1)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            print(f"  [ERROR] {desc} failed:")
            print(result.stderr or result.stdout)
            sys.exit(1)


def main():
    onedir = "--onedir" in sys.argv
    mode_label = "onedir" if onedir else "onefile"

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    t0 = time.time()

    print("=" * 45)
    print(f"  GHEval Build  ({mode_label})")
    print("=" * 45)
    print(f"  Python:     {sys.version.split()[0]}")
    print(f"  Platform:   {sys.platform}")
    print()

    # 1. Install dependencies
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
        "1/3  Installing dependencies")
    print("    Done.")
    print()

    # 2. Clean previous build
    print("  [2/3  Cleaning previous build]")
    build_sub = os.path.join(BUILD_DIR, "gheval")
    if os.path.isdir(build_sub):
        shutil.rmtree(build_sub)
        print(f"    Removed {build_sub}/")

    exe_name = "GHEval.exe" if sys.platform == "win32" else "GHEval"
    if onedir:
        out_dir = os.path.join(DIST_DIR, "GHEval")
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir)
            print(f"    Removed {out_dir}/")
    else:
        exe_path = os.path.join(DIST_DIR, exe_name)
        if os.path.exists(exe_path):
            os.remove(exe_path)
            print(f"    Removed {exe_path}")

    print("    Clean.")
    print()

    # 3. Build
    env = os.environ.copy()
    if onedir:
        env["GHEVAL_ONEDIR"] = "1"

    run([sys.executable, "-m", "PyInstaller", SPEC_FILE, "--noconfirm"],
        "3/3  Building executable", show_output=True, env=env)
    print()

    # 4. Report
    elapsed = time.time() - t0
    print("=" * 45)
    if onedir:
        out_dir = os.path.join(DIST_DIR, "GHEval")
        out_exe = os.path.join(out_dir, exe_name)
        if os.path.exists(out_exe):
            total = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, _, fns in os.walk(out_dir) for f in fns
            )
            print(f"  Build complete!  ({elapsed:.0f}s)")
            print(f"  Output: {os.path.abspath(out_dir)}/")
            print(f"  Size:   {total / (1024 * 1024):.1f} MB (folder)")
        else:
            print(f"  [WARNING] Expected {out_exe} not found.")
    else:
        exe_path = os.path.join(DIST_DIR, exe_name)
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"  Build complete!  ({elapsed:.0f}s)")
            print(f"  Output: {os.path.abspath(exe_path)}")
            print(f"  Size:   {size_mb:.1f} MB")
        else:
            print(f"  [WARNING] Expected {exe_path} not found.")
            print(f"  Check dist/ folder.")
    print("=" * 45)


if __name__ == "__main__":
    main()
