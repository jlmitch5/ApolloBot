#!/usr/bin/env python3
"""Install ApolloBot as a macOS system LaunchDaemon for the current user."""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import pwd
import subprocess
import sys
import tempfile
from pathlib import Path


LABEL = "com.apollobot.watcher"
PLIST_PATH = Path("/Library/LaunchDaemons") / f"{LABEL}.plist"
REPOSITORY = Path(__file__).resolve().parent
APP_SCRIPT = REPOSITORY / "apollobot.py"


def build_plist() -> dict[str, object]:
    account = pwd.getpwuid(os.getuid())
    home = Path(account.pw_dir)
    # Keep the invoked path (including any stable Homebrew symlink) so a
    # package upgrade doesn't pin the job to a versioned Cellar directory.
    python = Path(os.path.abspath(sys.executable))
    path_entries = dict.fromkeys(
        [str(python.parent), "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    )

    return {
        "Label": LABEL,
        "ProgramArguments": [str(python), str(APP_SCRIPT), "run"],
        "WorkingDirectory": str(REPOSITORY),
        "UserName": account.pw_name,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "EnvironmentVariables": {
            "HOME": str(home),
            "PATH": os.pathsep.join(path_entries),
            "PYTHONUNBUFFERED": "1",
        },
        "StandardOutPath": str(home / ".apollobot-launchd.log"),
        "StandardErrorPath": str(home / ".apollobot-launchd-error.log"),
    }


def run_sudo(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sudo", *arguments], check=check, text=True)


def install() -> None:
    if platform.system() != "Darwin":
        raise SystemExit("This installer is for macOS only.")
    if os.geteuid() == 0:
        raise SystemExit("Run this installer as your normal account, without sudo.")
    if not APP_SCRIPT.is_file():
        raise SystemExit(f"ApolloBot script not found: {APP_SCRIPT}")

    plist_data = plistlib.dumps(build_plist(), fmt=plistlib.FMT_XML)
    run_sudo("-v")

    # Remove an existing copy before replacing its plist, if it is currently loaded.
    loaded = subprocess.run(
        ["sudo", "launchctl", "print", f"system/{LABEL}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if loaded.returncode == 0:
        run_sudo("launchctl", "bootout", f"system/{LABEL}")

    with tempfile.NamedTemporaryFile() as generated_plist:
        generated_plist.write(plist_data)
        generated_plist.flush()
        run_sudo(
            "install",
            "-o",
            "root",
            "-g",
            "wheel",
            "-m",
            "644",
            generated_plist.name,
            str(PLIST_PATH),
        )

    run_sudo("launchctl", "bootstrap", "system", str(PLIST_PATH))
    print(f"Installed {LABEL} for {pwd.getpwuid(os.getuid()).pw_name}.")
    print(f"Repository: {REPOSITORY}")
    print(f"Python: {os.path.abspath(sys.executable)}")
    print("Check it with: apollobot status")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the generated launchd plist without installing it",
    )
    args = parser.parse_args()

    if args.dry_run:
        sys.stdout.buffer.write(plistlib.dumps(build_plist(), fmt=plistlib.FMT_XML))
        return 0

    install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
