"""Reject external binary distribution links before they reach the public repo.

GitHub-hosted Release assets are the only public distribution channel for this
project.  The guard deliberately checks links and tracked files, not ordinary
game text that merely contains words such as ``.zip``.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit


URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
REDIRECT_HOSTS = {
    "bit.ly",
    "cutt.ly",
    "goo.gl",
    "is.gd",
    "lnkd.in",
    "ow.ly",
    "rb.gy",
    "t.co",
    "tiny.cc",
    "tinyurl.com",
}
GITHUB_HOST_SUFFIXES = ("github.com", "githubusercontent.com")
BINARY_SUFFIXES = (
    ".7z",
    ".appimage",
    ".bin",
    ".com",
    ".dll",
    ".dmg",
    ".exe",
    ".jar",
    ".msi",
    ".pkg",
    ".rar",
    ".scr",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".whl",
    ".zip",
    ".argosmodel",
)
TRACKED_BINARY_SUFFIXES = BINARY_SUFFIXES + (".deb", ".rpm")


def _is_tracked_binary(path: Path) -> bool:
    lowered = path.name.lower()
    return any(lowered.endswith(suffix) for suffix in TRACKED_BINARY_SUFFIXES)


def _clean_url(value: str) -> str:
    return value.rstrip(".,;:!?)]}")


def _is_github_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    return host == "github.com" or any(host.endswith("." + suffix) for suffix in GITHUB_HOST_SUFFIXES)


def _looks_like_binary_download(path: str) -> bool:
    lowered = path.lower().rstrip("/")
    return lowered.endswith(BINARY_SUFFIXES)


def scan_text(text: str, *, source: str) -> list[str]:
    violations: list[str] = []
    for raw in URL_RE.findall(text):
        value = _clean_url(raw)
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            continue
        if host in REDIRECT_HOSTS:
            violations.append(f"{source}: shortened/redirect URL: {value}")
        elif not _is_github_host(host) and _looks_like_binary_download(parsed.path):
            violations.append(f"{source}: external binary download URL: {value}")
    return violations


def scan_repository(root: Path) -> list[str]:
    violations: list[str] = []
    try:
        import subprocess

        tracked = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "-z"], text=False
        ).decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("git ls-files failed") from exc
    for relative in (item for item in tracked if item):
        path = root / relative
        if _is_tracked_binary(path):
            violations.append(f"{relative}: tracked binary distribution file")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        violations.extend(scan_text(text, source=relative))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the repository for unsafe external binary distribution")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    violations = scan_repository(args.root.resolve())
    if violations:
        print("EXTERNAL_DISTRIBUTION_GUARD_FAILED")
        print("\n".join(violations))
        return 1
    print("EXTERNAL_DISTRIBUTION_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
