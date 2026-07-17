"""Focused tests for the Benge drawing annotation provider."""

from __future__ import annotations

from pathlib import Path

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

import config as cfg
import drawing_annotations

_TEST_ROOT = Path("/tmp/test_benge_annotations")


def _empty_model() -> DesignModel:
    return DesignModel(
        id="benge.property",
        name="Benge Property",
        artifact_stem="BengeProperty",
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


def _context(
    sheets: tuple[DrawingSheet, ...] | None = None,
) -> DrawingContext:
    return DrawingContext(
        project_root=_TEST_ROOT,
        config=cfg,
        model=_empty_model(),
        sheets=sheets or (_plan_sheet(),),
    )


def test_provider_id_and_provider_determinism() -> None:
    ctx = _context()
    first = drawing_annotations.build_annotations(ctx)
    second = drawing_annotations.build_annotations(ctx)
    assert first.provider_id == "benge.property.annotations"
    assert first == second


def test_annotations_cardinality_and_ids() -> None:
    result = drawing_annotations.build_annotations(_context())
    assert len(result.sheets) == 1
    sheet = result.sheets[0]
    assert sheet.sheet_id == "A-101"
    assert len(sheet.annotations) == 4
    ids = {ann.id for ann in sheet.annotations}
    assert ids == {
        "benge.annotation.section.a301",
        "benge.annotation.elevation.a201",
        "benge.annotation.elevation.a202",
        "benge.annotation.schedule.openings",
    }


def test_annotation_types() -> None:
    result = drawing_annotations.build_annotations(_context())
    ann = result.sheets[0].annotations
    types = sorted(type(a).__name__ for a in ann)
    assert types == ["ElevationMarker", "ElevationMarker", "SectionCallout", "Table"]


def test_section_callout_content() -> None:
    ctx = _context()
    result = drawing_annotations.build_annotations(ctx)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sec = ann["benge.annotation.section.a301"]
    assert isinstance(sec, SectionCallout)
    assert sec.sheet_id == "A-101"
    assert sec.reference_sheet_id == "A-301"
    assert sec.label == "A-301"
    assert sec.view_direction == "right"
    cut_x = to_mm(cfg.SECTION_CUT_X)
    assert sec.start == (cut_x, ctx.sheets[0].projected_bounds_mm[1])
    assert sec.end == (cut_x, ctx.sheets[0].projected_bounds_mm[3])


def test_elevation_markers_content() -> None:
    result = drawing_annotations.build_annotations(_context())
    ann = {a.id: a for a in result.sheets[0].annotations}
    e201 = ann["benge.annotation.elevation.a201"]
    assert isinstance(e201, ElevationMarker)
    assert e201.position == (5500.0, 1600.0)
    assert e201.reference_sheet_id == "A-201"
    assert e201.direction == "down"
    e202 = ann["benge.annotation.elevation.a202"]
    assert isinstance(e202, ElevationMarker)
    assert e202.position == (13500.0, -3500.0)
    assert e202.reference_sheet_id == "A-202"
    assert e202.direction == "left"


def test_schedule_content() -> None:
    result = drawing_annotations.build_annotations(_context())
    ann = {a.id: a for a in result.sheets[0].annotations}
    sched = ann["benge.annotation.schedule.openings"]
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


def test_schedule_derives_from_config() -> None:
    result = drawing_annotations.build_annotations(_context())
    ann = {a.id: a for a in result.sheets[0].annotations}
    sched = ann["benge.annotation.schedule.openings"]
    assert isinstance(sched, Table)
    row = sched.rows[0]
    expected_width = f'{drawing_annotations._format_opening(to_mm(cfg.DOOR_WIDTH))}'
    expected_height = f'{drawing_annotations._format_opening(to_mm(cfg.DOOR_HEIGHT))}'
    assert row.cells[2] == expected_width
    assert row.cells[3] == expected_height


def test_schedule_position_from_bounds() -> None:
    bounds = (-3000.0, -18000.0, 14000.0, 2500.0)
    ctx = _context(sheets=(_plan_sheet(bounds),))
    result = drawing_annotations.build_annotations(ctx)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sched = ann["benge.annotation.schedule.openings"]
    assert isinstance(sched, Table)
    min_x, min_y, max_x, _ = bounds
    expected_x = min_x + 0.04 * (max_x - min_x)
    expected_y = min_y + 1400.0
    assert sched.position == (expected_x, expected_y)


def test_invalid_context_missing_sheet() -> None:
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
    ctx = _context(sheets=other_sheets)
    raised = False
    try:
        drawing_annotations.build_annotations(ctx)
    except ValueError as exc:
        raised = True
        assert "A-101" in str(exc)
    assert raised


def test_no_file_writes_on_import() -> None:
    assert not _TEST_ROOT.exists() or not any(_TEST_ROOT.iterdir())


def test_no_file_writes_on_call(tmp_path: Path) -> None:
    ctx = DrawingContext(
        project_root=tmp_path,
        config=cfg,
        model=_empty_model(),
        sheets=(_plan_sheet(),),
    )
    result = drawing_annotations.build_annotations(ctx)
    assert isinstance(result, DrawingAnnotationSet)
    assert not any(tmp_path.iterdir())


def test_section_callout_bounds_tracking() -> None:
    bounds = (-5000.0, -25000.0, 20000.0, 5000.0)
    ctx = _context(sheets=(_plan_sheet(bounds),))
    result = drawing_annotations.build_annotations(ctx)
    ann = {a.id: a for a in result.sheets[0].annotations}
    sec = ann["benge.annotation.section.a301"]
    assert isinstance(sec, SectionCallout)
    assert sec.start[1] == bounds[1]
    assert sec.end[1] == bounds[3]


def test_annotation_ids_are_unique() -> None:
    result = drawing_annotations.build_annotations(_context())
    ids = [a.id for a in result.sheets[0].annotations]
    assert len(ids) == len(set(ids))
