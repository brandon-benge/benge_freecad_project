#!/usr/bin/env python3
"""Managed updater implementation that preserves downstream design source."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from install import (
    DEFAULT_SOURCE_URL,
    acquire_source,
    copy_missing_path,
    copy_path,
    ensure_agent_links,
    ensure_managed_executables,
    force_refreshable_specs,
    load_manifest,
    managed_specs,
    print_report,
    spec,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update managed Python CAD tooling safely.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Template directory, ZIP, GitHub repository, or ZIP URL.")
    parser.add_argument("--project-dir", default=".", help="Existing project directory.")
    parser.add_argument(
        "--force",
        "--force-guidance",
        "--force-project-files",
        action="store_true",
        dest="force_guidance",
        help="Restore force-refreshable project defaults; protected design source and tests are never replaced.",
    )
    parser.add_argument("--skip-legacy-removal", action="store_true", help="Keep explicitly listed obsolete managed paths for inspection.")
    return parser.parse_args(argv)


def update_from_source(source: Path, project: Path, *, force_guidance: bool = False, remove_legacy: bool = True) -> dict[str, list[str]]:
    """Refresh managed paths while leaving removed project seeds and unknown files untouched."""
    if not project.is_dir():
        raise RuntimeError(f"Project folder does not exist: {project}")
    manifest = load_manifest(source)
    protected = manifest.get("protected_project_files", manifest["project_owned_files"])
    report = {"managed": [], "seeded": [], "guidance": [], "preserved": list(protected), "removed": []}
    for source_name, destination_name in managed_specs(manifest):
        copy_path(source / source_name, project / destination_name)
        report["managed"].append(destination_name)
    ensure_managed_executables(project, manifest)
    for item in manifest["project_seed_files"]:
        source_name, destination_name = spec(item)
        destination = project / destination_name
        if destination.exists() or destination.is_symlink():
            continue
        copy_path(source / source_name, destination)
        report["seeded"].append(destination_name)
    for source_name, destination_name in force_refreshable_specs(manifest):
        destination = project / destination_name
        if (destination.exists() or destination.is_symlink()) and not force_guidance:
            copy_missing_path(source / source_name, destination)
            if destination_name not in report["preserved"]:
                report["preserved"].append(destination_name)
            continue
        copy_path(source / source_name, destination)
        report["guidance"].append(destination_name)
    if remove_legacy:
        for relative in manifest.get("remove_legacy_managed", []):
            target = project / relative
            if not target.exists() and not target.is_symlink():
                continue
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
            report["removed"].append(relative)
    ensure_agent_links(project)
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project = Path(args.project_dir).expanduser().resolve()
    with tempfile.TemporaryDirectory() as temp_name:
        source = acquire_source(args.source_url, Path(temp_name))
        report = update_from_source(source, project, force_guidance=args.force_guidance, remove_legacy=not args.skip_legacy_removal)
    print_report(report)
    print("\nManaged tool update complete; protected design source, project tests, generated outputs, and unknown files were preserved.")
    print("Viewer: ./start.sh")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Tool update failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
