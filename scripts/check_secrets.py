"""Scan publication files. Report categories and paths, never secret values."""
import argparse
from pathlib import Path
import re
import subprocess

PATTERNS = {
    "OpenAI-like key": re.compile(rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}"),
    "GitHub token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "AWS access key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "Private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if args.staged else [
        "git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    names = subprocess.check_output(command, cwd=root).decode("utf-8").split("\0")
    failures = []
    checked = 0
    for name in sorted(set(filter(None, names))):
        relative = Path(name)
        if relative.name.startswith(".env") or relative.suffix.lower() in (".pem", ".key", ".p12", ".pfx"):
            failures.append((name, "Forbidden secret file"))
        data = subprocess.check_output(["git", "show", ":" + name], cwd=root) if args.staged else (root / name).read_bytes()
        checked += 1
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                failures.append((name, label))
    for name, label in failures:
        print(f"BLOCKED {name}: {label}")
    print(f"Scanned {checked} files; findings: {len(failures)} (values never printed).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
