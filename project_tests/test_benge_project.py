from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import ezdxf
import ifcopenshell
from build123d import import_step
from pypdf import PdfReader
from python_cad_tools.build import build_project
from python_cad_tools.exporters.ifc import property_value

SOURCE_COMMIT = "76b8d75c88d606611a82d135a45fc9be7ce840fb"
FORMATS = ["step", "ifc", "glb", "drawings", "quantities"]
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_benge_project_builds_and_reconciles() -> None:
    build_project(PROJECT_ROOT, FORMATS)
    generated = PROJECT_ROOT / "generated"

    design = json.loads((generated / "manifests/design-elements.json").read_text(encoding="utf-8"))
    build = json.loads((generated / "manifests/build-manifest.json").read_text(encoding="utf-8"))
    ids = {element["id"] for element in design["elements"] if element["physical"]}
    assert build["validation_status"] == "passed"
    assert build["model_element_count"] == 236
    assert design["metadata"]["source_commit"] == SOURCE_COMMIT
    assert {
        "complex.house.house_mass",
        "complex.fireplace.fireplace_masonry_body",
        "complex.feature.hot_tub_placeholder",
        "complex.outdoor_kitchen.outdoor_kitchen_cabinet_run",
        "complex.pool.pool_water_34x12_5ft_to8ft",
        "complex.roof.upper_deck_full_cover",
        "complex.stair.lower_front_tread_01",
        "complex.structure.hot_tub_platform",
    } <= ids

    step_path = generated / "step/BengeComplexFunctional.step"
    step_validation = json.loads((generated / "step/validation.json").read_text(encoding="utf-8"))
    assert step_validation["valid"] is True
    assert len(import_step(step_path).solids()) == len(ids)

    ifc = ifcopenshell.open(generated / "ifc/BengeComplexFunctional.ifc")
    ifc_ids = {property_value(entity, "StableId") for entity in ifc.by_type("IfcBuildingElementProxy")}
    ifc_validation = json.loads((generated / "ifc/validation.json").read_text(encoding="utf-8"))
    assert ifc_validation["valid"] is True
    assert ifc_ids == ids

    glb = json.loads((generated / "glb/manifest.json").read_text(encoding="utf-8"))
    assert set(glb["elements"]) == ids
    assert glb["bounds_cad_mm"] == step_validation["bounds_mm"]

    quantities = json.loads((generated / "quantities/quantities.json").read_text(encoding="utf-8"))
    assert {row["element_id"] for row in quantities} == ids
    assert all(row["volume_mm3"] > 0 for row in quantities)

    svg_paths = sorted((generated / "drawings/svg").glob("*.svg"))
    dxf_paths = sorted((generated / "drawings/dxf").glob("*.dxf"))
    assert len(svg_paths) == len(dxf_paths) == 4
    plan = ET.parse(generated / "drawings/svg/BengeComplexFunctional_plan.svg").getroot()
    plan_source_ids = {element.attrib.get("data-source-id") for element in plan.iter()}
    assert {
        "complex.house.house_mass",
        "complex.pool.pool_water_34x12_5ft_to8ft",
        "complex.feature.hot_tub_placeholder",
    } <= plan_source_ids
    assert "Conceptual — not for construction or permitting" in "".join(plan.itertext())

    for path in dxf_paths:
        assert not ezdxf.readfile(path).audit().has_errors
    pdf = PdfReader(generated / "drawings/pdf/BengeComplexFunctional_Conceptual_Drawings.pdf")
    assert len(pdf.pages) == 4
    assert all("Conceptual" in (page.extract_text() or "") for page in pdf.pages)
