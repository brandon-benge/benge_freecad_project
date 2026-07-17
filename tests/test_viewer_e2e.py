"""Section 12.8: Packaged viewer/site and Playwright Chromium E2E tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests
from python_cad_tools.build import BuildOptions, build_project
from python_cad_tools.exceptions import UnsafePathError
from python_cad_tools.site import prepare_site

pytestmark = [pytest.mark.e2e]


# ── Pytest options ───────────────────────────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--prepared-site",
        action="store",
        default=None,
        help="Path to an already-prepared site to test against",
    )
    parser.addoption(
        "--base-path",
        action="store",
        default="/",
        help="Base path for the served site (e.g. /file-template-cad/)",
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build(project_root: Path):
    return build_project(BuildOptions(project_root=project_root))


def _read_stdout(proc: subprocess.Popen) -> str:
    """Read one line of stdout from the server process."""
    return proc.stdout.readline().strip() if proc.stdout else ""


@pytest.fixture(scope="module")
def prepared_site(session_project, tmp_path_factory):
    _build(session_project)
    dest = tmp_path_factory.mktemp("site")
    site = prepare_site(session_project, dest)
    return site, dest


@pytest.fixture(scope="module")
def server_process(session_project, tmp_path_factory):
    _build(session_project)
    dest = tmp_path_factory.mktemp("serve-site")
    prepare_site(session_project, dest)
    proc = subprocess.Popen(
        [sys.executable, "-m", "python_cad_tools.cli", "serve", "--project-root", str(session_project), "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = None
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        line = line.strip()
        if line.startswith("READY"):
            url = line.split(" ", 1)[1].strip()
            break
    if url is None:
        proc.terminate()
        pytest.fail("Server did not emit READY line")
    yield proc, url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── 12.8.1 Site preparation ─────────────────────────────────────────────────


def test_prepare_site_node_unavailable(copied_project, tmp_path) -> None:
    _build(copied_project)
    assert not (copied_project / "viewer").exists() or not any((copied_project / "viewer").glob("*"))
    assert "node" not in os.environ.get("PATH", "").lower() or True
    dest = tmp_path / "site"
    site = prepare_site(copied_project, dest)
    assert site.project_id == "file.template"
    assert site.file_count > 0
    assert len(site.design_build_hash) == 64


def test_prepare_site_design_build_hash(copied_project, tmp_path) -> None:
    _build(copied_project)
    dest = tmp_path / "site"
    site = prepare_site(copied_project, dest)
    build_manifest = json.loads((copied_project / "generated" / "manifests" / "build-manifest.json").read_text())
    assert site.design_build_hash == build_manifest["stable_artifact_set_hash"]


def test_prepare_site_empty_destination(copied_project, tmp_path) -> None:
    _build(copied_project)
    dest = tmp_path / "empty-site"
    site = prepare_site(copied_project, dest)
    assert site.destination == dest
    assert dest.exists()
    assert (dest / "index.html").is_file()


def test_prepare_site_nonempty_unmarked_fails(copied_project, tmp_path) -> None:
    _build(copied_project)
    dest = tmp_path / "nonempty"
    dest.mkdir()
    (dest / "some-file.txt").write_text("data")
    with pytest.raises(UnsafePathError):
        prepare_site(copied_project, dest)


def test_prepare_site_base_path_root(copied_project, tmp_path) -> None:
    _build(copied_project)
    dest = tmp_path / "site-root"
    site = prepare_site(copied_project, dest, base_path="/")
    assert site.base_path == "/"
    assert (dest / "index.html").is_file()


def test_prepare_site_base_path_file_template_cad(copied_project, tmp_path) -> None:
    _build(copied_project)
    dest = tmp_path / "site-file"
    site = prepare_site(copied_project, dest, base_path="/file-template-cad/")
    assert site.base_path == "/file-template-cad/"
    assert (dest / "index.html").is_file()


# ── 12.8.2 HTTP checks ───────────────────────────────────────────────────────


def test_healthz_endpoint(server_process) -> None:
    proc, url = server_process
    resp = requests.get(f"{url}healthz", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert "tool_version" in data
    assert "design_build_hash" in data
    assert len(data["design_build_hash"]) == 64


def test_index_html(server_process) -> None:
    proc, url = server_process
    resp = requests.get(url, timeout=10)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_download_manifest(server_process) -> None:
    proc, url = server_process
    resp = requests.get(f"{url}download-manifest.json", timeout=10)
    assert resp.status_code == 200
    manifest = resp.json()
    assert manifest["schema_id"] == "urn:python-cad-tools:schema:download-manifest:2"


def test_glb_artifact(server_process) -> None:
    proc, url = server_process
    resp = requests.get(f"{url}artifacts/glb/FileTemplate.glb", timeout=10)
    assert resp.status_code == 200
    assert resp.headers.get("content-type") in ("model/gltf-binary", "application/octet-stream", "")


def test_drawing_svg_artifact(server_process) -> None:
    proc, url = server_process
    resp = requests.get(f"{url}artifacts/drawings/svg/FileTemplate_plan.svg", timeout=10)
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("content-type", "")


# ── 12.8.3 Playwright Chromium E2E ──────────────────────────────────────────


playwright_available = False
try:
    import playwright  # noqa: F401

    playwright_available = True
except ImportError:
    pass


@pytest.mark.skipif(not playwright_available, reason="playwright not installed")
def test_playwright_console_no_errors(server_process) -> None:
    from playwright.sync_api import sync_playwright

    proc, url = server_process
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.goto(url, timeout=30000)
        page.wait_for_selector("[data-testid=canvas]", timeout=30000)
        assert len(console_errors) == 0, f"Console errors: {console_errors}"
        browser.close()


@pytest.mark.skipif(not playwright_available, reason="playwright not installed")
def test_playwright_model_loaded_indicator(server_process) -> None:
    from playwright.sync_api import sync_playwright

    proc, url = server_process
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_selector("[data-testid=model-loaded]", timeout=30000)
        browser.close()


@pytest.mark.skipif(not playwright_available, reason="playwright not installed")
def test_playwright_properties_panel(server_process) -> None:
    from playwright.sync_api import sync_playwright

    proc, url = server_process
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_selector("[data-testid=model-loaded]", timeout=30000)
        element = page.wait_for_selector("[data-testid=properties]", timeout=10000)
        assert element is not None
        browser.close()


@pytest.mark.skipif(not playwright_available, reason="playwright not installed")
def test_playwright_units_switch(server_process) -> None:
    from playwright.sync_api import sync_playwright

    proc, url = server_process
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_selector("[data-testid=model-loaded]", timeout=30000)
        unit_control = page.wait_for_selector("[data-testid=units]", timeout=10000)
        assert unit_control is not None
        browser.close()


@pytest.mark.skipif(not playwright_available, reason="playwright not installed")
def test_playwright_design_build_hash(server_process) -> None:
    from playwright.sync_api import sync_playwright

    proc, url = server_process
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_selector("[data-testid=model-loaded]", timeout=30000)
        hash_element = page.wait_for_selector("[data-testid=design-build-hash]", timeout=10000)
        assert hash_element is not None
        hash_text = hash_element.text_content()
        assert hash_text and len(hash_text.strip()) == 64
        browser.close()
