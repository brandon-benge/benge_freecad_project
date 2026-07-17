"""Section 12.3: Annotation contract tests."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from python_cad_tools.context import DrawingContext
from python_cad_tools.drawings import (
    DrawingAnnotationSet,
    DrawingSheet,
    ElevationMarker,
    SectionCallout,
    Table,
)
from python_cad_tools.elements import DesignModel
from python_cad_tools.units import to_mm


def _empty_model() -> DesignModel:
    return DesignModel(
        id="file.template",
        name="File Template",
        artifact_stem="FileTemplate",
        elements=[],
    )


def _plan_sheet(
    bounds: tuple[float, float, float, float] = (-2000.0, -20000.0, 15000.0, 3000.0),
) -> DrawingSheet:
    return DrawingSheet(
        sheet_id="A-101",
        view_id="plan",
        origin_mm=(0.0, 0.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        projected_bounds_mm=bounds,
    )


def _load_config(copied_project: Path) -> ModuleType:
    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("config", "drawing_annotations"):
            del sys.modules[mod]
    try:
        import config as cfg

        return cfg
    finally:
        sys.path.remove(str(copied_project))


def _context(
    copied_project: Path,
    sheets: tuple[DrawingSheet, ...] | None = None,
) -> DrawingContext:
    cfg = _load_config(copied_project)
    return DrawingContext(
        project_root=copied_project,
        config=cfg,
        model=_empty_model(),
        sheets=sheets or (_plan_sheet(),),
    )


def _build_annotations(
    copied_project: Path,
    ctx: DrawingContext | None = None,
) -> DrawingAnnotationSet:
    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("drawing_annotations", "config"):
            del sys.modules[mod]
    try:
        import drawing_annotations as da

        if ctx is None:
            ctx = _context(copied_project)
        return da.build_annotations(ctx)
    finally:
        sys.path.remove(str(copied_project))


def test_provider_id_and_provider_determinism(copied_project) -> None:
    ctx = _context(copied_project)
    first = _build_annotations(copied_project, ctx)
    second = _build_annotations(copied_project, ctx)
    assert first.provider_id == "file.template.annotations"
    assert first == second


def test_annotations_cardinality_and_ids(copied_project) -> None:
    result = _build_annotations(copied_project)
    assert len(result.sheets) == 1
    sheet = result.sheets[0]
    assert sheet.sheet_id == "A-101"
    assert len(sheet.annotations) == 4
    ids = {ann.id for ann in sheet.annotations}
    assert ids == {
        "file.annotation.section.a301",
        "file.annotation.elevation.a201",
        "file.annotation.elevation.a202",
        "file.annotation.schedule.openings",
    }


def test_annotation_types(copied_project) -> None:
    result = _build_annotations(copied_project)
    ann = result.sheets[0].annotations
    types = sorted(type(a).__name__ for a in ann)
    assert types == ["ElevationMarker", "ElevationMarker", "SectionCallout", "Table"]


def test_section_callout_content(copied_project) -> None:
    ctx = _context(copied_project)
    result = _build_annotations(copied_project, ctx)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sec = ann["file.annotation.section.a301"]
    assert isinstance(sec, SectionCallout)
    assert sec.sheet_id == "A-101"
    assert sec.reference_sheet_id == "A-301"
    assert sec.label == "A-301"
    assert sec.view_direction == "right"
    cut_x = to_mm(ctx.config.SECTION_CUT_X)
    assert sec.start == (cut_x, ctx.sheets[0].projected_bounds_mm[1])
    assert sec.end == (cut_x, ctx.sheets[0].projected_bounds_mm[3])


def test_elevation_markers_content(copied_project) -> None:
    result = _build_annotations(copied_project)
    ann = {a.id: a for a in result.sheets[0].annotations}
    e201 = ann["file.annotation.elevation.a201"]
    assert isinstance(e201, ElevationMarker)
    assert e201.position == (5500.0, 1600.0)
    assert e201.reference_sheet_id == "A-201"
    assert e201.direction == "down"
    e202 = ann["file.annotation.elevation.a202"]
    assert isinstance(e202, ElevationMarker)
    assert e202.position == (13500.0, -3500.0)
    assert e202.reference_sheet_id == "A-202"
    assert e202.direction == "left"


def test_schedule_content(copied_project) -> None:
    cfg = _load_config(copied_project)
    result = _build_annotations(copied_project)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sched = ann["file.annotation.schedule.openings"]
    assert isinstance(sched, Table)
    assert sched.title == "DOOR & WINDOW SCHEDULE"
    assert sched.columns == ("Opening", "Type", "Width", "Height")
    assert len(sched.rows) == 1
    row = sched.rows[0]
    assert row.id == "SD-01"
    assert row.cells[0] == "SD-01"
    assert row.cells[1] == "Sliding Glass Door"
    width_mm = round(to_mm(cfg.DOOR_WIDTH))
    height_mm = round(to_mm(cfg.DOOR_HEIGHT))
    assert f"{width_mm:,}mm" in row.cells[2]
    assert f"{height_mm:,}mm" in row.cells[3]


def test_schedule_derives_from_config(copied_project) -> None:
    cfg = _load_config(copied_project)
    result = _build_annotations(copied_project)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sched = ann["file.annotation.schedule.openings"]
    assert isinstance(sched, Table)
    row = sched.rows[0]
    width_mm = to_mm(cfg.DOOR_WIDTH)
    height_mm = to_mm(cfg.DOOR_HEIGHT)
    assert f"{round(width_mm):,}mm" in row.cells[2]
    assert f"{round(height_mm):,}mm" in row.cells[3]


def test_schedule_position_from_bounds(copied_project) -> None:
    bounds = (-3000.0, -18000.0, 14000.0, 2500.0)
    ctx = _context(copied_project, sheets=(_plan_sheet(bounds),))
    result = _build_annotations(copied_project, ctx)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sched = ann["file.annotation.schedule.openings"]
    assert isinstance(sched, Table)
    min_x, min_y, max_x, _ = bounds
    expected_x = min_x + 0.04 * (max_x - min_x)
    expected_y = min_y + 1400.0
    assert sched.position == (expected_x, expected_y)


def test_invalid_context_missing_sheet(copied_project) -> None:
    other_sheets = (
        DrawingSheet(
            sheet_id="A-999",
            view_id="plan",
            origin_mm=(0.0, 0.0, 0.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
            projected_bounds_mm=(0.0, 0.0, 100.0, 100.0),
        ),
    )
    ctx = _context(copied_project, sheets=other_sheets)
    raised = False
    try:
        _build_annotations(copied_project, ctx)
    except ValueError as exc:
        raised = True
        assert "A-101" in str(exc)
    assert raised


def test_no_file_writes_on_import(copied_project) -> None:
    assert not any(copied_project.rglob("*.svg"))
    assert not any(copied_project.rglob("*.dxf"))
    assert not any(copied_project.rglob("*.pdf"))


def test_no_file_writes_on_call(copied_project, tmp_path) -> None:
    clean_dir = tmp_path / "call_test"
    clean_dir.mkdir()
    cfg = _load_config(copied_project)
    ctx = DrawingContext(
        project_root=clean_dir,
        config=cfg,
        model=_empty_model(),
        sheets=(_plan_sheet(),),
    )
    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("drawing_annotations", "config"):
            del sys.modules[mod]
    try:
        import drawing_annotations as da

        result = da.build_annotations(ctx)
    finally:
        sys.path.remove(str(copied_project))
    assert isinstance(result, DrawingAnnotationSet)
    assert not any(clean_dir.iterdir())


def test_section_callout_bounds_tracking(copied_project) -> None:
    bounds = (-5000.0, -25000.0, 20000.0, 5000.0)
    ctx = _context(copied_project, sheets=(_plan_sheet(bounds),))
    result = _build_annotations(copied_project, ctx)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sec = ann["file.annotation.section.a301"]
    assert isinstance(sec, SectionCallout)
    assert sec.start[1] == bounds[1]
    assert sec.end[1] == bounds[3]


def test_annotation_ids_are_unique(copied_project) -> None:
    result = _build_annotations(copied_project)
    ids = [a.id for a in result.sheets[0].annotations]
    assert len(ids) == len(set(ids))
