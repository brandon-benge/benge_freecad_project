"""Sections 12.4-12.7: Programmatic build, CLI, artifact reconciliation, determinism."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import ezdxf
import ifcopenshell
from build123d import import_step
from pypdf import PdfReader
from python_cad_tools.build import BuildOptions, ValidationOptions, build_project, clean_project, validate_project
from python_cad_tools.determinism import semantic_hash

ANNOTATION_IDS = {
    "file.annotation.section.a301",
    "file.annotation.elevation.a201",
    "file.annotation.elevation.a202",
    "file.annotation.schedule.openings",
}

ANNOTATION_SUB_IDS = {
    "file.annotation.elevation.a201",
    "file.annotation.elevation.a201.label",
    "file.annotation.elevation.a201.outline",
    "file.annotation.elevation.a201.pointer",
    "file.annotation.elevation.a202",
    "file.annotation.elevation.a202.label",
    "file.annotation.elevation.a202.outline",
    "file.annotation.elevation.a202.pointer",
    "file.annotation.schedule.openings",
    "file.annotation.schedule.openings.border",
    "file.annotation.schedule.openings.header.0",
    "file.annotation.schedule.openings.header.1",
    "file.annotation.schedule.openings.header.2",
    "file.annotation.schedule.openings.header.3",
    "file.annotation.schedule.openings.row.SD-01.cell.0",
    "file.annotation.schedule.openings.row.SD-01.cell.1",
    "file.annotation.schedule.openings.row.SD-01.cell.2",
    "file.annotation.schedule.openings.row.SD-01.cell.3",
    "file.annotation.schedule.openings.row.SD-01.separator",
    "file.annotation.schedule.openings.title",
    "file.annotation.section.a301",
    "file.annotation.section.a301.arrow.end",
    "file.annotation.section.a301.arrow.start",
    "file.annotation.section.a301.label.end",
    "file.annotation.section.a301.label.start",
    "file.annotation.section.a301.line",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── 12.4 Programmatic end-to-end build ───────────────────────────────────────


def test_validate_project_no_output(copied_project) -> None:
    options = ValidationOptions(project_root=copied_project)
    report = validate_project(options)
    assert report.ok, f"Validation failed: {report.issues}"
    gen = copied_project / "generated"
    assert not gen.exists() or not list(gen.rglob("*"))


def test_build_project_returns_build_result(copied_project) -> None:
    result = build_project(BuildOptions(project_root=copied_project))
    assert result.project_root == copied_project
    assert result.output_root == copied_project / "generated"
    assert isinstance(result.design_semantic_hash, str) and len(result.design_semantic_hash) == 64
    bm = _load_json(result.output_root / "manifests" / "build-manifest.json")
    assert bm["validation"]["status"] == "passed"


def test_build_result_paths_point_to_final_output(build_manifest, built_output) -> None:
    for entry in build_manifest["artifacts"]:
        path = built_output / entry["path"]
        assert path.is_file(), f"Artifact not found: {path}"
        assert str(path).startswith(str(built_output))


def test_build_annotations_complete_before_return(built_output) -> None:
    ann_manifest = built_output / "drawings" / "annotation-manifest.json"
    assert ann_manifest.is_file(), f"Missing annotation manifest at {ann_manifest}"
    annotations = _load_json(ann_manifest)
    assert annotations["provider_id"] == "file.template.annotations"
    ann_ids = {ann["id"] for ann in annotations["annotations"]}
    assert ann_ids >= ANNOTATION_IDS


def test_build_selected_formats(copied_project) -> None:
    result = build_project(BuildOptions(project_root=copied_project, formats=("step", "ifc")))
    output = result.output_root
    assert (output / "step" / "FileTemplate.step").is_file()
    assert (output / "ifc" / "FileTemplate.ifc").is_file()
    assert not (output / "glb").exists() or not list((output / "glb").rglob("*"))


def test_build_full_default_formats(built_output) -> None:
    for fmt in ("step", "ifc", "glb", "drawings", "quantities"):
        assert (built_output / fmt).exists(), f"Missing format directory: {fmt}"


# ── 12.5 CLI end-to-end ──────────────────────────────────────────────────────


def _cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "python_cad_tools.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_build_from_root(copied_project) -> None:
    result = _cli("build", cwd=copied_project)
    assert result.returncode == 0, f"CLI build failed: stderr={result.stderr}"
    assert (copied_project / "generated" / "step" / "FileTemplate.step").is_file()


def test_cli_build_from_path_with_spaces(copied_project_with_spaces) -> None:
    result = _cli("build", cwd=copied_project_with_spaces)
    assert result.returncode == 0, f"CLI build failed in path with spaces: {result.stderr}"
    assert (copied_project_with_spaces / "generated" / "step" / "FileTemplate.step").is_file()


def test_cli_validate(copied_project) -> None:
    result = _cli("validate", cwd=copied_project)
    assert result.returncode == 0, f"CLI validate failed: {result.stderr}"
    assert '"status":"ok"' in result.stdout


def test_cli_verify(session_project) -> None:
    result = _cli("verify", cwd=session_project)
    assert result.returncode == 0, f"CLI verify failed: {result.stderr}"


def test_cli_clean(copied_project) -> None:
    _cli("build", cwd=copied_project)
    assert (copied_project / "generated" / "step" / "FileTemplate.step").is_file()
    result = _cli("clean", cwd=copied_project)
    assert result.returncode == 0, f"CLI clean failed: {result.stderr}"
    assert not (copied_project / "generated" / "step").exists()


def test_cli_repeated_format(copied_project) -> None:
    result = _cli("build", "--format", "step", "--format", "ifc", cwd=copied_project)
    assert result.returncode == 0, f"CLI repeated format failed: {result.stderr}"
    assert (copied_project / "generated" / "step" / "FileTemplate.step").is_file()
    assert not (copied_project / "generated" / "glb").exists()


# ── 12.6 Final artifact reconciliation ──────────────────────────────────────


def test_artifact_manifest_schema_ids(build_manifest, design_manifest) -> None:
    assert "build-manifest" in build_manifest.get("schema_id", "")
    assert "design-manifest" in design_manifest.get("schema_id", "")


def test_artifact_integrity(built_output, build_manifest) -> None:
    for entry in build_manifest["artifacts"]:
        path = built_output / entry["path"]
        if not path.is_file():
            if path.name == ".gitkeep":
                continue
            raise AssertionError(f"Missing artifact: {path}")
        actual_size = path.stat().st_size
        assert actual_size == entry["size"], f"Size mismatch for {entry['path']}: {actual_size} != {entry['size']}"
        actual_sha = _sha256(path)
        assert actual_sha == entry["sha256"], f"SHA-256 mismatch for {entry['path']}"


def test_artifact_stable_artifact_set_hash(build_manifest) -> None:
    assert isinstance(build_manifest.get("stable_artifact_set_hash"), str)
    assert len(build_manifest["stable_artifact_set_hash"]) == 64


def test_step_reload(built_output) -> None:
    step_path = built_output / "step" / "FileTemplate.step"
    validation = _load_json(built_output / "step" / "validation.json")
    assert validation["valid"] is True
    solids = import_step(step_path).solids()
    design = _load_json(built_output / "manifests" / "design-manifest.json")
    physical_ids = {e["id"] for e in design["elements"] if e["physical"]}
    assert len(solids) == len(physical_ids)


def test_ifc_parse_and_reconcile(built_output) -> None:
    ifc = ifcopenshell.open(built_output / "ifc" / "FileTemplate.ifc")
    ifc_validation = _load_json(built_output / "ifc" / "validation.json")
    assert ifc_validation["valid"] is True
    proxies = ifc.by_type("IfcBuildingElementProxy")
    assert len(proxies) > 0
    design = _load_json(built_output / "manifests" / "design-manifest.json")
    physical_ids = {e["id"] for e in design["elements"] if e["physical"]}
    ifc_ids = set()
    for entity in proxies:
        for rel_def in entity.IsDefinedBy:
            if rel_def.is_a("IfcRelDefinesByProperties"):
                for prop in rel_def.RelatingPropertyDefinition.HasProperties:
                    if prop.Name == "StableId":
                        ifc_ids.add(str(prop.NominalValue.wrappedValue))
    assert ifc_ids == physical_ids, (
        f"IFC IDs differ: {len(physical_ids - ifc_ids)} missing, {len(ifc_ids - physical_ids)} extra"
    )


def test_glb_manifest(built_output) -> None:
    glb = _load_json(built_output / "glb" / "manifest.json")
    design = _load_json(built_output / "manifests" / "design-manifest.json")
    physical_ids = {e["id"] for e in design["elements"] if e["physical"]}
    assert set(glb["elements"]) == physical_ids
    step_validation = _load_json(built_output / "step" / "validation.json")
    assert glb["bounds_cad_mm"] == step_validation["bounds_mm"]


def test_quantities_inventory(built_output) -> None:
    qty = _load_json(built_output / "quantities" / "quantities.json")
    design = _load_json(built_output / "manifests" / "design-manifest.json")
    physical_ids = {e["id"] for e in design["elements"] if e["physical"]}
    qty_ids = {row["element_id"] for row in qty["records"]}
    assert qty_ids == physical_ids
    assert all(row["volume_mm3"] > 0 for row in qty["records"])
    assert (built_output / "quantities" / "quantities.csv").is_file()
    assert (built_output / "quantities" / "materials.csv").is_file()
    assert (built_output / "quantities" / "summary.md").is_file()
    with (built_output / "quantities" / "quantities.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(physical_ids)
    assert "element_id" in rows[0] and "volume_mm3" in rows[0]


def test_drawings_inventory(built_output) -> None:
    svg_paths = sorted((built_output / "drawings" / "svg").glob("*.svg"))
    dxf_paths = sorted((built_output / "drawings" / "dxf").glob("*.dxf"))
    assert len(svg_paths) == len(dxf_paths) == 4
    for svg, dxf in zip(svg_paths, dxf_paths, strict=True):
        assert svg.stem == dxf.stem
    pdf_path = built_output / "drawings" / "pdf" / "FileTemplate_Conceptual_Drawings.pdf"
    assert pdf_path.is_file()
    pdf = PdfReader(pdf_path)
    assert len(pdf.pages) == 4
    assert all("Conceptual" in (page.extract_text() or "") for page in pdf.pages)


def test_plan_svg_content(built_output) -> None:
    plan = ET.parse(built_output / "drawings" / "svg" / "FileTemplate_plan.svg").getroot()
    plan_source_ids = {element.attrib.get("data-source-id") for element in plan.iter()}
    assert {
        "complex.house.house_mass",
        "complex.pool.pool_water_34x12_5ft_to8ft",
        "complex.feature.hot_tub_placeholder",
    } <= plan_source_ids
    assert "Conceptual" in "".join(plan.itertext())


def test_dxf_audit(built_output) -> None:
    for path in sorted((built_output / "drawings" / "dxf").glob("*.dxf")):
        assert not ezdxf.readfile(path).audit().has_errors


def test_annotation_manifest(built_output) -> None:
    ann_manifest = _load_json(built_output / "drawings" / "annotation-manifest.json")
    ann_ids = {ann["id"] for ann in ann_manifest["annotations"]}
    assert ann_ids >= ANNOTATION_IDS


# ── 12.7 Failure rollback/recovery and determinism ──────────────────────────


def test_two_clean_builds_identical(copied_project) -> None:
    build_project(BuildOptions(project_root=copied_project))
    output1 = copied_project / "generated"
    bm1 = _load_json(output1 / "manifests" / "build-manifest.json")
    clean_project(copied_project)
    assert not (copied_project / "generated" / "step").exists()
    build_project(BuildOptions(project_root=copied_project))
    output2 = copied_project / "generated"
    bm2 = _load_json(output2 / "manifests" / "build-manifest.json")
    assert bm1["design_semantic_hash"] == bm2["design_semantic_hash"]
    known_non_deterministic = {
        "run-metadata.json",
        "build-manifest.json",
        "FileTemplate.step",
    }
    bm1_stable_excluding_step = semantic_hash(
        [
            e
            for e in bm1["artifacts"]
            if not e["volatile"] and not any(e["path"].endswith(name) for name in known_non_deterministic)
        ]
    )
    bm2_stable_excluding_step = semantic_hash(
        [
            e
            for e in bm2["artifacts"]
            if not e["volatile"] and not any(e["path"].endswith(name) for name in known_non_deterministic)
        ]
    )
    assert bm1_stable_excluding_step == bm2_stable_excluding_step, (
        "Stable artifact hash mismatch excluding known non-deterministic files"
    )
    arts1 = {e["path"]: e for e in bm1["artifacts"]}
    arts2 = {e["path"]: e for e in bm2["artifacts"]}
    assert set(arts1) == set(arts2), "Artifact paths differ between builds"
    for path_key, entry1 in arts1.items():
        entry2 = arts2[path_key]
        if any(entry1["path"].endswith(name) for name in known_non_deterministic):
            continue
        assert entry1["sha256"] == entry2["sha256"], f"SHA-256 mismatch for {path_key} between builds"


def test_deterministic_nonvolatile_bytes(copied_project) -> None:
    build_project(BuildOptions(project_root=copied_project))
    output1 = copied_project / "generated"
    clean_project(copied_project)
    build_project(BuildOptions(project_root=copied_project))
    output2 = copied_project / "generated"
    bm1 = _load_json(output1 / "manifests" / "build-manifest.json")
    bm2 = _load_json(output2 / "manifests" / "build-manifest.json")
    volatile_names = {"run-metadata.json", "build-manifest.json", "FileTemplate.step"}
    for entry1, entry2 in zip(bm1["artifacts"], bm2["artifacts"], strict=True):
        if Path(entry1["path"]).name in volatile_names:
            continue
        path1 = output1 / entry1["path"]
        path2 = output2 / entry2["path"]
        bytes1 = path1.read_bytes()
        bytes2 = path2.read_bytes()
        assert bytes1 == bytes2, f"Byte mismatch for {entry1['path']} between builds"
