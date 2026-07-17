"""Section 12.2: In-memory model contract tests.

Verifies the model matches the reviewed golden contract in
tests/fixtures/model_contract_v1.json.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from python_cad_tools.context import BuildContext
from python_cad_tools.elements import DesignModel
from python_cad_tools.validation import fatal_issues, validate_model

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "model_contract_v1.json"
SELECTED_ELEMENT_IDS = (
    "complex.feature.hot_tub_placeholder",
    "complex.fireplace.fireplace_masonry_body",
    "complex.house.house_mass",
    "complex.outdoor_kitchen.outdoor_kitchen_cabinet_run",
    "complex.pool.pool_water_34x12_5ft_to8ft",
    "complex.roof.upper_deck_full_cover",
    "complex.stair.lower_front_tread_01",
    "complex.structure.hot_tub_platform",
)


def _build_model(project_root: Path) -> DesignModel:
    sys.path.insert(0, str(project_root))
    for mod in list(sys.modules):
        if mod in ("config", "model") or mod.startswith("config.") or mod.startswith("model."):
            del sys.modules[mod]
    try:
        import config
        import model as model_mod

        context = BuildContext(project_root, config, source_revision="test", source_dirty=True)
        return model_mod.build_model(context)
    finally:
        sys.path.remove(str(project_root))


def test_model_identity(copied_project) -> None:
    model = _build_model(copied_project)
    assert model.id == "file.template"
    assert model.name == "File Template"
    assert model.artifact_stem == "FileTemplate"
    assert model.metadata["project"] == "File Template CAD"


def test_model_no_fatal_issues(copied_project) -> None:
    model = _build_model(copied_project)
    issues = validate_model(model)
    assert not fatal_issues(issues), f"Fatal validation issues: {issues}"


def test_model_element_count(copied_project) -> None:
    model = _build_model(copied_project)
    elements = list(model.walk())
    assert len(elements) == 236


def test_model_all_element_ids_start_with_complex(copied_project) -> None:
    model = _build_model(copied_project)
    for element in model.walk():
        assert element.id.startswith("complex."), f"Unexpected element ID: {element.id}"


def test_model_element_ids_unique(copied_project) -> None:
    model = _build_model(copied_project)
    ids = [element.id for element in model.walk()]
    assert len(ids) == len(set(ids))


def test_model_required_ids_present(copied_project) -> None:
    model = _build_model(copied_project)
    ids = {element.id for element in model.walk()}
    for required in SELECTED_ELEMENT_IDS:
        assert required in ids, f"Required element ID missing: {required}"


def test_model_all_ids_in_golden(copied_project) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    golden_ids = set(fixture["element_ids"])
    model = _build_model(copied_project)
    model_ids = {element.id for element in model.walk()}
    assert model_ids == golden_ids, (
        f"Model has {len(model_ids - golden_ids)} extra and {len(golden_ids - model_ids)} missing IDs"
    )


def test_model_material_ids(copied_project) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    golden_material_ids = set(fixture["material_ids"])
    model = _build_model(copied_project)
    material_ids = set()
    for element in model.walk():
        if element.material is not None:
            material_ids.add(element.material.id)
    assert material_ids == golden_material_ids


def test_model_material_densities_positive(copied_project) -> None:
    model = _build_model(copied_project)
    for element in model.walk():
        if element.material is not None and element.material.density_kg_m3 is not None:
            assert element.material.density_kg_m3 > 0


def _bounds(element) -> list[float]:
    box = element.geometry.bounding_box()
    return [*box.min, *box.max]


def test_model_bounds_match_golden(copied_project) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    golden_bounds = fixture["model_bounds_mm"]
    model = _build_model(copied_project)
    all_bounds = [_bounds(element) for element in model.walk()]
    model_bounds = [
        min(b[index] for b in all_bounds) if index < 3 else max(b[index] for b in all_bounds) for index in range(6)
    ]
    for i in range(6):
        assert abs(model_bounds[i] - golden_bounds[i]) < 0.1, (
            f"Model bounds mismatch at index {i}: {model_bounds[i]} != {golden_bounds[i]}"
        )


def test_model_no_file_writes_on_import(copied_project) -> None:
    generated = copied_project / "generated"
    if generated.exists():
        for p in generated.rglob("*"):
            p.unlink()
        generated.rmdir()
    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("config", "model") or mod.startswith("config.") or mod.startswith("model."):
            del sys.modules[mod]
    try:
        import config
        import model as model_mod

        context = BuildContext(copied_project, config, source_revision="test", source_dirty=True)
        model_mod.build_model(context)
        assert not generated.exists() or not any(generated.iterdir())
    finally:
        sys.path.remove(str(copied_project))


def test_source_sha256_match_golden(copied_project) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    golden = fixture["baseline"]["source_sha256"]
    for name in ("config.py", "model.py"):
        path = copied_project / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == golden[name], f"{name} SHA-256 does not match golden"


def test_model_categories_consistent(copied_project) -> None:
    model = _build_model(copied_project)
    categories = {element.category for element in model.walk()}
    assert categories == {
        "deck-board",
        "deck-framing",
        "feature",
        "fireplace",
        "house",
        "outdoor-kitchen",
        "pool",
        "railing",
        "roof",
        "roof-framing",
        "site",
        "skirting",
        "stair",
        "structure",
    }
