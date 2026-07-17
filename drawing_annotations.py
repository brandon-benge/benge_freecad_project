"""Format-neutral Benge drawing annotation provider.

Usage:
    from python_cad_tools.context import DrawingContext
    from python_cad_tools.drawings import DrawingAnnotationSet

    annotations = build_annotations(context)
"""

from __future__ import annotations

from python_cad_tools.context import DrawingContext
from python_cad_tools.drawings import (
    DrawingAnnotationSet,
    ElevationMarker,
    SectionCallout,
    SheetAnnotations,
    Table,
    TableRow,
)
from python_cad_tools.units import format_feet_inches, to_mm

PROVIDER_ID = "benge.property.annotations"


def _format_opening(value_mm: float) -> str:
    return f'{format_feet_inches(value_mm)} ({round(value_mm):,}mm)'


def _find_sheet(
    context: DrawingContext, sheet_id: str,
) -> tuple[float, float, float, float]:
    for sheet in context.sheets:
        if sheet.sheet_id == sheet_id:
            return sheet.projected_bounds_mm
    raise ValueError(f"Required sheet {sheet_id} not found in drawing context")


def build_annotations(context: DrawingContext) -> DrawingAnnotationSet:
    config = context.config
    bounds = _find_sheet(context, "A-101")
    min_x, min_y, max_x, max_y = bounds

    cut_x = to_mm(config.SECTION_CUT_X)

    section_callout = SectionCallout(
        id="benge.annotation.section.a301",
        sheet_id="A-101",
        start=(cut_x, min_y),
        end=(cut_x, max_y),
        reference_sheet_id="A-301",
        label="A-301",
        view_direction="right",
    )

    elev_a201 = ElevationMarker(
        id="benge.annotation.elevation.a201",
        sheet_id="A-101",
        position=(5500.0, 1600.0),
        reference_sheet_id="A-201",
        label="A-201",
        direction="down",
    )

    elev_a202 = ElevationMarker(
        id="benge.annotation.elevation.a202",
        sheet_id="A-101",
        position=(13500.0, -3500.0),
        reference_sheet_id="A-202",
        label="A-202",
        direction="left",
    )

    width_mm = to_mm(config.DOOR_WIDTH)
    height_mm = to_mm(config.DOOR_HEIGHT)
    schedule = Table(
        id="benge.annotation.schedule.openings",
        sheet_id="A-101",
        position=(min_x + 0.04 * (max_x - min_x), min_y + 1400.0),
        title="DOOR & WINDOW SCHEDULE",
        columns=("Opening", "Type", "Width", "Height"),
        rows=(
            TableRow(
                id="SD-01",
                cells=(
                    "SD-01",
                    "Sliding Glass Door",
                    _format_opening(width_mm),
                    _format_opening(height_mm),
                ),
            ),
        ),
    )

    return DrawingAnnotationSet(
        provider_id=PROVIDER_ID,
        sheets=(
            SheetAnnotations(
                sheet_id="A-101",
                annotations=(
                    section_callout,
                    elev_a201,
                    elev_a202,
                    schedule,
                ),
            ),
        ),
    )
