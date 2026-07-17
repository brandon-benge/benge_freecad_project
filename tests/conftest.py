from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from python_cad_tools.build import BuildOptions, build_project


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _copy_project(src: Path, dest: Path) -> None:
    ignores = {
        "generated",
        ".venv",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".mypy",
        ".back_agents",
        ".back_opencode",
        "node_modules",
        ".tools",
        "viewer",
        "backup",
        ".claude",
        ".codex",
        ".github",
        "site",
    }
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        name = item.name
        if name in ignores or name.startswith("."):
            continue
        if item.is_dir():
            shutil.copytree(item, dest / name, symlinks=False, ignore=shutil.ignore_patterns("__pycache__"))
        elif item.is_file():
            shutil.copy2(item, dest / name)


@pytest.fixture
def copied_project(repo_root: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "project"
    _copy_project(repo_root, dest)
    return dest


@pytest.fixture
def copied_project_with_spaces(repo_root: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "my project with spaces" / "file"
    _copy_project(repo_root, dest)
    return dest


@pytest.fixture(scope="session")
def session_project(repo_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("session_project")
    _copy_project(repo_root, dest)
    return dest


@pytest.fixture(scope="session")
def built_project(session_project: Path) -> Path:
    build_project(BuildOptions(project_root=session_project))
    return session_project


@pytest.fixture(scope="session")
def built_output(built_project: Path) -> Path:
    return built_project / "generated"


@pytest.fixture(scope="session")
def build_manifest(built_output: Path) -> dict:
    return json.loads((built_output / "manifests" / "build-manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def design_manifest(built_output: Path) -> dict:
    return json.loads((built_output / "manifests" / "design-manifest.json").read_text(encoding="utf-8"))


@pytest.fixture
def project_import(copied_project: Path) -> Generator[None, None, None]:
    sys.path.insert(0, str(copied_project))
    prefixes = ("config.", "model.", "drawing_annotations.")
    for mod in list(sys.modules):
        if mod in ("config", "model", "drawing_annotations") or any(mod.startswith(p) for p in prefixes):
            del sys.modules[mod]
    try:
        yield
    finally:
        sys.path.remove(str(copied_project))
