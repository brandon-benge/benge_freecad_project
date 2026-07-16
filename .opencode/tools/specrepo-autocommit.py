#!/usr/bin/env python3
"""Run the LangChain AutoCommit CLI for a verified SpecRepo change."""

from __future__ import annotations

import os
import shutil
import site
import subprocess
import sys
from pathlib import Path

AUTOCOMMIT_REPOSITORY = (
    "git+https://github.com/brandon-benge/langchain_autocommit.git"
)
CONFIGURATION_GUIDE = (
    "https://github.com/brandon-benge/langchain_autocommit/"
    "blob/main/README.md#config-overrides"
)
EX_USAGE = 64


def print_usage() -> None:
    print(
        "Usage: specrepo-autocommit \"<summary of what changed>\"\n\n"
        "Runs autocommit on the current git branch.\n"
        "AUTOCOMMIT_PARAMS must point to an existing YAML configuration file.",
        file=sys.stderr,
    )


def fail(message: str, *, config_path: Path | None = None, code: int = 1) -> None:
    print(message, file=sys.stderr)
    if config_path is not None:
        print(f"AUTOCOMMIT_PARAMS location: {config_path}", file=sys.stderr)
        print(
            "Update that file as needed. Configuration guide: "
            f"{CONFIGURATION_GUIDE}",
            file=sys.stderr,
        )
    raise SystemExit(code)


def get_config_path() -> Path:
    raw_path = os.environ.get("AUTOCOMMIT_PARAMS", "").strip()
    if not raw_path:
        fail(
            "Autocommit blocked: AUTOCOMMIT_PARAMS is not set. Set it to the "
            "YAML configuration file described at "
            f"{CONFIGURATION_GUIDE}."
        )

    config_path = Path(os.path.expandvars(raw_path)).expanduser().resolve()
    print(f"AUTOCOMMIT_PARAMS is set to: {config_path}", flush=True)

    if not config_path.is_file():
        fail(
            "Autocommit blocked: the AUTOCOMMIT_PARAMS file does not exist or "
            "is not a regular file.",
            config_path=config_path,
        )

    return config_path


def get_current_branch(config_path: Path) -> str:
    try:
        symbolic_ref = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        branch = symbolic_ref.stdout.strip()

        if not branch:
            revision = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
            branch = revision.stdout.strip()
    except OSError as error:
        fail(
            f"Autocommit blocked: could not run git: {error}",
            config_path=config_path,
        )

    if not branch:
        fail(
            "Autocommit blocked: could not determine the current git branch.",
            config_path=config_path,
        )

    return branch


def find_autocommit() -> str | None:
    executable = shutil.which("autocommit")
    if executable:
        return executable

    scripts_directory = Path(site.getuserbase()) / (
        "Scripts" if os.name == "nt" else "bin"
    )
    candidate = scripts_directory / (
        "autocommit.exe" if os.name == "nt" else "autocommit"
    )
    return str(candidate) if candidate.is_file() else None


def ensure_autocommit_installed(config_path: Path) -> str:
    executable = find_autocommit()
    if executable:
        return executable

    print("autocommit CLI not found. Installing it with the current Python...")
    try:
        installation = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--user",
                AUTOCOMMIT_REPOSITORY,
            ],
            check=False,
        )
    except OSError as error:
        fail(
            f"Autocommit installation failed: {error}",
            config_path=config_path,
        )

    if installation.returncode != 0:
        fail(
            "Autocommit installation failed with exit code "
            f"{installation.returncode}.",
            config_path=config_path,
            code=installation.returncode,
        )

    executable = find_autocommit()
    if not executable:
        fail(
            "Autocommit was installed but its executable could not be found.",
            config_path=config_path,
        )

    print("autocommit installed successfully.")
    return executable


def run_autocommit(
    executable: str, config_path: Path, summary: str, branch: str
) -> None:
    print(f"Running autocommit on branch {branch}.")
    try:
        result = subprocess.run(
            [
                executable,
                "--yes",
                "--config-file",
                str(config_path),
                "-c",
                summary,
            ],
            check=False,
        )
    except OSError as error:
        fail(
            f"Autocommit failed to start: {error}",
            config_path=config_path,
        )

    if result.returncode != 0:
        fail(
            f"Autocommit failed with exit code {result.returncode}.",
            config_path=config_path,
            code=result.returncode if result.returncode > 0 else 1,
        )


def main(argv: list[str]) -> int:
    config_path = get_config_path()

    if len(argv) < 2 or not " ".join(argv[1:]).strip():
        print_usage()
        fail(
            "Autocommit blocked: a summary of what changed is required.",
            config_path=config_path,
            code=EX_USAGE,
        )

    summary = " ".join(argv[1:]).strip()
    branch = get_current_branch(config_path)
    executable = ensure_autocommit_installed(config_path)
    run_autocommit(executable, config_path, summary, branch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
