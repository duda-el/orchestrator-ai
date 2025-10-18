import argparse
import tempfile
import shutil
import subprocess
import os
from pathlib import Path
import sys
import json

# Add the parent directory to the Python path to allow imports from 'core'
sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.analyzer import analyze_repository


def clone_repo(repo_url: str) -> str:
    """
    Clone the given repo URL into a new temporary directory.
    Returns the path to the temp directory.
    """
    tmpdir = tempfile.mkdtemp(prefix="orchai_")
    try:
        # --depth 1 keeps it fast (shallow clone)
        subprocess.check_call(["git", "clone", "--depth", "1", repo_url, tmpdir])
        return tmpdir
    except subprocess.CalledProcessError as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise SystemExit(f"❌ git clone failed: {e}")


def cmd_analyze(repo_url: str):
    print("🔧 analyze called")
    print(f"→ repo_url = {repo_url}")

    # 1) clone repo into a temp folder
    repo_path = clone_repo(repo_url)
    print(f"📦 cloned into: {repo_path}")

    # 2) Analyze the repository
    print("🔍 analyzing repository...")
    analysis_result = analyze_repository(repo_path)
    print("\n--- Analysis Result ---")
    print(json.dumps(analysis_result, indent=4))
    print("-----------------------\n")


    # NOTE: we'll keep the temp folder for step 3 (analysis).
    # If you want to clean it up right now, uncomment:
    shutil.rmtree(repo_path, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(prog="orchai", description="Orchestrator AI CLI (MVP)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # orchai analyze <repo_url>
    p_analyze = sub.add_parser("analyze", help="Analyze a repo and (later) generate Docker/compose files")
    p_analyze.add_argument("repo_url", help="Git or GitHub URL")

    args = parser.parse_args()

    if args.cmd == "analyze":
        cmd_analyze(args.repo_url)

if __name__ == "__main__":
    main()
