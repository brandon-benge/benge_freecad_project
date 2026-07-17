#!/usr/bin/env python3
"""Generate and verify the reviewed pre-migration semantic model contract."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import ifcopenshell

from python_cad_tools.context import BuildContext


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "model_contract_v1.json"
BASELINE_HEAD = "a82127eb725f18e69891303138a63804658fc6a6"
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


def _rounded(value: float) -> float:
    result = round(float(value), 6)
    return 0.0 if result == -0.0 else result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_baseline_model() -> Any:
    original_register = atexit.register
    atexit.register = lambda function, *args, **kwargs: function  # type: ignore[assignment]
    try:
        for name in ("drawing_annotations", "model", "config"):
            sys.modules.pop(name, None)
        sys.path.insert(0, str(ROOT))
        try:
            import config
            import model

            context = BuildContext(ROOT, config, BASELINE_HEAD, source_dirty=False)
            return model.build_model(context)
        finally:
            sys.path.remove(str(ROOT))
    finally:
        atexit.register = original_register


def _bounds(element: Any) -> list[float]:
    box = element.geometry.bounding_box()
    return [_rounded(value) for value in (*tuple(box.min), *tuple(box.max))]


def _quantity_record(element: Any) -> dict[str, Any]:
    material = element.material
    volume_mm3 = _rounded(element.geometry.volume)
    area_mm2 = _rounded(element.geometry.area)
    density = material.density_kg_m3 if material is not None else None
    mass_kg = _rounded(volume_mm3 / 1_000_000_000 * density) if density is not None else None
    return {
        "area_mm2": area_mm2,
        "category": element.category,
        "count": 1,
        "element_id": element.id,
        "mass_kg": mass_kg,
        "material_id": material.id if material is not None else None,
        "volume_mm3": volume_mm3,
    }


def _aggregate(records: list[dict[str, Any]], key: str | None = None) -> Any:
    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        masses = [row["mass_kg"] for row in rows if row["mass_kg"] is not None]
        return {
            "area_mm2": _rounded(sum(row["area_mm2"] for row in rows)),
            "count": sum(row["count"] for row in rows),
            "mass_kg": _rounded(sum(masses)) if masses else None,
            "volume_mm3": _rounded(sum(row["volume_mm3"] for row in rows)),
        }

    if key is None:
        return summarize(records)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        group = record[key]
        if group is not None:
            grouped[str(group)].append(record)
    return {name: summarize(grouped[name]) for name in sorted(grouped)}


def _legacy_ifc_spatial() -> list[dict[str, Any]]:
    path = ROOT / "generated" / "ifc" / "BengeProperty.ifc"
    if not path.is_file():
        raise AssertionError(f"baseline IFC is missing: {path}")
    ifc = ifcopenshell.open(path)
    records: list[dict[str, Any]] = []
    for ifc_class in ("IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey"):
        entities = ifc.by_type(ifc_class)
        if len(entities) != 1:
            raise AssertionError(f"expected one {ifc_class}, found {len(entities)}")
        entity = entities[0]
        records.append(
            {
                "ifc_class": ifc_class,
                "legacy_global_id": entity.GlobalId,
                "legacy_name": entity.Name,
                "relation": None,
            }
        )
    for entity in ifc.by_type("IfcRelAggregates"):
        relating = entity.RelatingObject
        related = entity.RelatedObjects
        records.append(
            {
                "ifc_class": "IfcRelAggregates",
                "legacy_global_id": entity.GlobalId,
                "legacy_name": None,
                "relation": {
                    "from": relating.is_a(),
                    "to": [item.is_a() for item in related],
                },
            }
        )
    return records


def _identity_migration(spatial: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_stem": {"legacy": "BengeComplexFunctional", "target": "BengeProperty"},
        "element_ids": {"policy": "preserve_exactly", "prefix": "complex."},
        "ifc_product_global_ids": {"policy": "preserve_with_element_ids"},
        "ifc_spatial_and_aggregate_global_ids": {
            "deterministic_model_id_input": {
                "legacy": "functional.benge_complex",
                "target": "benge.property",
            },
            "legacy_observations": spatial,
            "policy": "migrate_once",
            "target_observation": None,
            "target_observation_note": (
                "Prompt 01 cannot change model identity or fabricate candidate-package output; "
                "the canonical target build must observe and verify the new IDs."
            ),
        },
        "material_ids": {"policy": "preserve_exactly", "prefix": "material.complex."},
        "model_id": {"legacy": "functional.benge_complex", "target": "benge.property"},
        "model_name": {"legacy": "BengeComplexFunctional", "target": "Benge Property"},
        "output_filename_stem": {"legacy": "BengeComplexFunctional", "target": "BengeProperty"},
        "project_tag": {"legacy": "complex-functional", "target": "benge-property"},
        "source_module": {"legacy": "functional.benge_complex.model", "target": "model"},
    }


def build_contract() -> dict[str, Any]:
    model = _load_baseline_model()
    elements = list(model.walk())
    element_ids = sorted(element.id for element in elements)
    if len(element_ids) != len(set(element_ids)):
        raise AssertionError("baseline model has duplicate element IDs")
    if len(element_ids) != 236:
        raise AssertionError(f"expected 236 baseline elements, found {len(element_ids)}")
    if not all(element_id.startswith("complex.") for element_id in element_ids):
        raise AssertionError("baseline contains a non-complex.* element ID")

    material_ids = sorted(
        {element.material.id for element in elements if element.material is not None}
    )
    records = [_quantity_record(element) for element in elements if element.physical]
    all_bounds = [_bounds(element) for element in elements]
    model_bounds = [
        min(bounds[index] for bounds in all_bounds) if index < 3 else max(bounds[index] for bounds in all_bounds)
        for index in range(6)
    ]
    selected_bounds = {element_id: _bounds(model.get(element_id)) for element_id in SELECTED_ELEMENT_IDS}

    contract = {
        "baseline": {
            "element_count": len(element_ids),
            "head": BASELINE_HEAD,
            "model_id": model.id,
            "model_name": model.name,
            "model_metadata": model.metadata,
            "source_sha256": {
                "config.py": _sha256(ROOT / "config.py"),
                "model.py": _sha256(ROOT / "model.py"),
            },
        },
        "contract": "benge-property-cad-model-contract-v1",
        "element_ids": element_ids,
        "identity_migration": _identity_migration(_legacy_ifc_spatial()),
        "material_ids": material_ids,
        "model_bounds_mm": model_bounds,
        "quantity_aggregates": {
            "by_category": _aggregate(records, "category"),
            "by_material": _aggregate(records, "material_id"),
            "totals": _aggregate(records),
        },
        "schema_version": 1,
        "selected_bounds_mm": selected_bounds,
    }
    _validate_internal_consistency(contract)
    return contract


def _validate_internal_consistency(contract: dict[str, Any]) -> None:
    element_ids = contract["element_ids"]
    material_ids = contract["material_ids"]
    assert contract["schema_version"] == 1
    assert contract["contract"] == "benge-property-cad-model-contract-v1"
    assert len(element_ids) == contract["baseline"]["element_count"] == 236
    assert element_ids == sorted(set(element_ids))
    assert material_ids == sorted(set(material_ids))
    assert set(contract["selected_bounds_mm"]) == set(SELECTED_ELEMENT_IDS)
    assert all(len(bounds) == 6 for bounds in contract["selected_bounds_mm"].values())
    assert len(contract["model_bounds_mm"]) == 6
    totals = contract["quantity_aggregates"]["totals"]
    by_category = contract["quantity_aggregates"]["by_category"]
    by_material = contract["quantity_aggregates"]["by_material"]
    assert totals["count"] == sum(group["count"] for group in by_category.values()) == 236
    assert totals["count"] == sum(group["count"] for group in by_material.values())
    assert set(by_material) == set(material_ids)
    identity = contract["identity_migration"]
    assert identity["model_id"] == {
        "legacy": "functional.benge_complex",
        "target": "benge.property",
    }
    assert identity["element_ids"]["policy"] == "preserve_exactly"
    assert identity["material_ids"]["policy"] == "preserve_exactly"
    spatial = identity["ifc_spatial_and_aggregate_global_ids"]["legacy_observations"]
    assert len(spatial) == 7
    assert len({record["legacy_global_id"] for record in spatial}) == 7


def _verify_generated_semantics(contract: dict[str, Any]) -> None:
    design_path = ROOT / "generated" / "manifests" / "design-manifest.json"
    quantities_path = ROOT / "generated" / "quantities" / "quantities.json"
    step_validation_path = ROOT / "generated" / "step" / "validation.json"
    for path in (design_path, quantities_path, step_validation_path):
        if not path.is_file():
            raise AssertionError(f"baseline semantic artifact is missing: {path}")

    design = json.loads(design_path.read_text(encoding="utf-8"))
    quantities = json.loads(quantities_path.read_text(encoding="utf-8"))
    step_validation = json.loads(step_validation_path.read_text(encoding="utf-8"))
    assert design["model_id"] == contract["baseline"]["model_id"]
    assert design["model_name"] == contract["baseline"]["model_name"]
    assert sorted(element["id"] for element in design["elements"]) == contract["element_ids"]
    assert sorted({element["material_id"] for element in design["elements"]}) == contract["material_ids"]
    assert {
        element_id: next(
            element["bounds_mm"] for element in design["elements"] if element["id"] == element_id
        )
        for element_id in SELECTED_ELEMENT_IDS
    } == contract["selected_bounds_mm"]
    assert step_validation["bounds_mm"] == contract["model_bounds_mm"]

    normalized_quantities = [
        {
            "area_mm2": _rounded(row["area_mm2"]),
            "category": row["category"],
            "count": row["count"],
            "element_id": row["element_id"],
            "mass_kg": _rounded(row["mass_kg"]) if row["mass_kg"] is not None else None,
            "material_id": row["material_id"],
            "volume_mm3": _rounded(row["volume_mm3"]),
        }
        for row in quantities["records"]
    ]
    assert {
        "by_category": _aggregate(normalized_quantities, "category"),
        "by_material": _aggregate(normalized_quantities, "material_id"),
        "totals": _aggregate(normalized_quantities),
    } == contract["quantity_aggregates"]
    assert _legacy_ifc_spatial() == contract["identity_migration"][
        "ifc_spatial_and_aggregate_global_ids"
    ]["legacy_observations"]


def verify() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _validate_internal_consistency(fixture)
    expected = build_contract()
    if fixture != expected:
        raise AssertionError(
            "model_contract_v1.json does not match the untouched baseline model; "
            "run this verifier with --write only for an explicitly reviewed baseline change"
        )
    _verify_generated_semantics(fixture)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the reviewed fixture")
    args = parser.parse_args()
    if args.write:
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
        ).stdout.strip()
        if current_head != BASELINE_HEAD:
            raise AssertionError(f"refusing to generate from {current_head}; expected {BASELINE_HEAD}")
        contract = build_contract()
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _verify_generated_semantics(contract)
        print(f"WROTE {FIXTURE}")
    else:
        verify()
        print(f"PASS {FIXTURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
