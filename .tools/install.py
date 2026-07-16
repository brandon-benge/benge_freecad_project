#!/usr/bin/env python3
"""Managed installer implementation for Python-first CAD projects."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_URL = "https://github.com/brandon-benge/freecad_macro_project_template"
MANIFEST = Path(".tools/manifest.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a headless Python CAD project from this template.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Template directory, ZIP, GitHub repository, or ZIP URL.")
    parser.add_argument("--project-dir", required=True, help="Destination project directory.")
    parser.add_argument("--force", action="store_true", help="Allow a non-empty destination; project-owned files remain preserved.")
    parser.add_argument(
        "--replace-project-files",
        action="store_true",
        help="Deprecated alias for --force-guidance; protected design source is never replaced.",
    )
    parser.add_argument(
        "--force-guidance",
        action="store_true",
        help="Restore force-refreshable project defaults; protected design source is never replaced.",
    )
    return parser.parse_args(argv)


def normalize_source_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.endswith(".zip"):
        return value
    if value.startswith("https://github.com/") and "/archive/" not in value:
        return f"{value}/archive/refs/heads/main.zip"
    return value


def acquire_source(value: str, temp_dir: Path) -> Path:
    local = Path(value).expanduser()
    if local.is_dir():
        return local.resolve()
    archive_path = temp_dir / "template.zip"
    if local.is_file():
        shutil.copy2(local, archive_path)
    else:
        urllib.request.urlretrieve(normalize_source_url(value), archive_path)
    extract_dir = temp_dir / "source"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)
    children = [path for path in extract_dir.iterdir() if path.is_dir()]
    return children[0] if len(children) == 1 else extract_dir


def load_manifest(source: Path) -> dict[str, Any]:
    path = source / MANIFEST
    if not path.exists():
        raise RuntimeError(f"Template manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def copy_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True, ignore=_managed_copy_ignores)
    else:
        shutil.copy2(source, destination)


def _managed_copy_ignores(directory: str, names: list[str]) -> set[str]:
    ignored = set(shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "dist", "coverage")(directory, names))
    current = Path(directory)
    if current.name == "model" and current.parent.name == "public":
        ignored.update(name for name in names if name != ".gitignore")
    return ignored


def copy_missing_path(source: Path, destination: Path) -> None:
    """Seed absent guidance entries without replacing existing customizations."""
    if not destination.exists() and not destination.is_symlink():
        copy_path(source, destination)
        return
    if not source.is_dir() or source.is_symlink() or not destination.is_dir() or destination.is_symlink():
        return
    for child in source.iterdir():
        copy_missing_path(child, destination / child.name)


def spec(value: str | dict[str, str]) -> tuple[str, str]:
    if isinstance(value, str):
        return value, value
    return value["source"], value["destination"]


def managed_specs(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    """Return validated managed mappings before an installer or updater writes them."""
    result: list[tuple[str, str]] = []
    destinations: set[str] = set()
    project_owned = set(manifest.get("project_owned_files", []))
    for item in manifest["managed_files"]:
        source_name, destination_name = spec(item)
        destination = Path(destination_name)
        if destination.is_absolute() or ".." in destination.parts or destination_name in {"", "."}:
            raise RuntimeError(f"Unsafe managed destination in template manifest: {destination_name}")
        if destination_name in destinations:
            raise RuntimeError(f"Duplicate managed destination in template manifest: {destination_name}")
        if destination_name in project_owned:
            raise RuntimeError(f"Managed destination is also project-owned: {destination_name}")
        destinations.add(destination_name)
        result.append((source_name, destination_name))
    return result


def ensure_managed_executables(project: Path, manifest: dict[str, Any]) -> None:
    """Restore executable bits that archive extraction may discard."""
    managed = {destination for _, destination in managed_specs(manifest)}
    for relative in manifest.get("executable_managed_files", []):
        if relative not in managed:
            raise RuntimeError(f"Executable path is not managed: {relative}")
        target = project / relative
        if not target.is_file():
            raise RuntimeError(f"Managed executable is missing: {target}")
        target.chmod(target.stat().st_mode | 0o111)


def force_refreshable_specs(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    """Return safe project defaults that an explicit force option may restore."""
    items = manifest.get("force_refreshable_files", manifest.get("force_refreshable_guidance", []))
    protected = set(manifest.get("protected_project_files", []))
    managed = {destination for _, destination in managed_specs(manifest)}
    result: list[tuple[str, str]] = []
    destinations: set[str] = set()
    for item in items:
        source_name, destination_name = spec(item)
        destination = Path(destination_name)
        if destination.is_absolute() or ".." in destination.parts or destination_name in {"", "."}:
            raise RuntimeError(f"Unsafe force-refreshable destination in template manifest: {destination_name}")
        if destination_name in destinations:
            raise RuntimeError(f"Duplicate force-refreshable destination in template manifest: {destination_name}")
        if any(destination == Path(path) or destination in Path(path).parents or Path(path) in destination.parents for path in protected):
            raise RuntimeError(f"Protected project path is force-refreshable: {destination_name}")
        if destination_name in managed:
            raise RuntimeError(f"Managed destination is also force-refreshable: {destination_name}")
        destinations.add(destination_name)
        result.append((source_name, destination_name))
    return result


def install_from_source(
    source: Path,
    project: Path,
    *,
    force: bool = False,
    replace_project_files: bool = False,
    force_guidance: bool = False,
) -> dict[str, list[str]]:
    """Install the current distribution without deleting paths from older seed sets."""
    project.mkdir(parents=True, exist_ok=True)
    if any(project.iterdir()) and not force:
        raise RuntimeError(f"Project folder is not empty: {project}; use --force to preserve existing project files")
    manifest = load_manifest(source)
    report: dict[str, list[str]] = {"managed": [], "seeded": [], "preserved": [], "guidance": []}
    for source_name, destination_name in managed_specs(manifest):
        copy_path(source / source_name, project / destination_name)
        report["managed"].append(destination_name)
    ensure_managed_executables(project, manifest)
    for item in manifest["project_seed_files"]:
        source_name, destination_name = spec(item)
        destination = project / destination_name
        if destination.exists() or destination.is_symlink():
            report["preserved"].append(destination_name)
            continue
        copy_path(source / source_name, destination)
        report["seeded"].append(destination_name)
    refresh_defaults = force_guidance or replace_project_files
    for source_name, destination_name in force_refreshable_specs(manifest):
        destination = project / destination_name
        if (destination.exists() or destination.is_symlink()) and not refresh_defaults:
            copy_missing_path(source / source_name, destination)
            report["preserved"].append(destination_name)
            continue
        copy_path(source / source_name, destination)
        report["guidance"].append(destination_name)
    ensure_agent_links(project)
    return report


def ensure_agent_links(project: Path) -> None:
    for directory in (".claude", ".codex", ".opencode"):
        tool_dir = project / directory
        tool_dir.mkdir(parents=True, exist_ok=True)
        for name, target in (("agents", "../.agents/agents"), ("skills", "../.agents/skills")):
            link = tool_dir / name
            if not link.exists() and not link.is_symlink():
                link.symlink_to(target)
    claude = project / "CLAUDE.md"
    if not claude.exists() and not claude.is_symlink():
        claude.symlink_to("AGENTS.md")


def print_report(report: dict[str, list[str]]) -> None:
    labels = {
        "managed": "Installed managed paths",
        "seeded": "Seeded project-owned paths",
        "guidance": "Installed or refreshed project defaults",
        "preserved": "Preserved existing paths",
        "removed": "Removed explicitly declared legacy managed paths",
    }
    for key in ("managed", "seeded", "guidance", "preserved", "removed"):
        if report.get(key):
            print(f"\n{labels[key]}:")
            for path in report[key]:
                print(f"- {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project = Path(args.project_dir).expanduser().resolve()
    with tempfile.TemporaryDirectory() as temp_name:
        source = acquire_source(args.source_url, Path(temp_name))
        report = install_from_source(
            source, project, force=args.force, replace_project_files=args.replace_project_files, force_guidance=args.force_guidance
        )
    print_report(report)
    print("\nSetup: python -m venv .venv && .venv/bin/pip install -r .tools/requirements/runtime.lock")
    print("Build: python build.py")
    print("Viewer: ./start.sh")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Install failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
