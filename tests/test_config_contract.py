"""Section 12.1: Config contract tests."""

from __future__ import annotations

import sys

from python_cad_tools.units import to_mm


def test_config_dimensions_positive(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert cfg.PROJECT_NAME == "File Template"

    for name, value in vars(cfg).items():
        if name.endswith("_COLOR"):
            assert len(value) == 3
            for channel in value:
                assert 0.0 <= channel <= 1.0


def test_deck_elevations(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.LOWER_DECK_ELEVATION) > 0
    assert to_mm(cfg.UPPER_DECK_ELEVATION) > to_mm(cfg.LOWER_DECK_ELEVATION)
    assert to_mm(cfg.DECK_THICKNESS) > 0
    assert to_mm(cfg.DECK_BOARD_WIDTH) > 0
    assert to_mm(cfg.DECK_BOARD_GAP) > 0
    assert to_mm(cfg.JOIST_WIDTH) > 0
    assert to_mm(cfg.JOIST_HEIGHT) > to_mm(cfg.JOIST_WIDTH)
    assert to_mm(cfg.JOIST_SPACING) > to_mm(cfg.JOIST_WIDTH)
    assert to_mm(cfg.BEAM_WIDTH) > 0
    assert to_mm(cfg.BEAM_HEIGHT) > to_mm(cfg.BEAM_WIDTH)
    assert to_mm(cfg.SUPPORT_POST_SIZE) > 0


def test_roof_parameters(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.ROOF_HEIGHT_ABOVE_UPPER) > 0
    assert to_mm(cfg.ROOF_THICKNESS) > 0
    assert to_mm(cfg.ROOF_OVERHANG) > 0
    assert to_mm(cfg.ROOF_FASCIA_HEIGHT) > 0
    assert to_mm(cfg.ROOF_RAFTER_WIDTH) > 0
    assert to_mm(cfg.ROOF_RAFTER_HEIGHT) > to_mm(cfg.ROOF_RAFTER_WIDTH)
    assert to_mm(cfg.ROOF_RAFTER_SPACING) > to_mm(cfg.ROOF_RAFTER_WIDTH)


def test_stair_parameters(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.STAIR_WIDTH) > 0
    assert to_mm(cfg.TREAD_DEPTH) > 0
    assert to_mm(cfg.MAX_RISER) > 0
    assert to_mm(cfg.MAX_RISER) < to_mm(cfg.TREAD_DEPTH)
    assert to_mm(cfg.LANDING_DEPTH) > 0


def test_pool_dimensions(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.POOL_LENGTH) > 0
    assert to_mm(cfg.POOL_WIDTH) > 0
    assert to_mm(cfg.POOL_SHALLOW_DEPTH) > 0
    assert to_mm(cfg.POOL_DEEP_DEPTH) > to_mm(cfg.POOL_SHALLOW_DEPTH)
    assert to_mm(cfg.PATIO_BORDER) > 0
    assert to_mm(cfg.DECK_TO_POOL_CLEARANCE) > 0


def test_hot_tub_and_fireplace(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.HOT_TUB_WIDTH) > 0
    assert to_mm(cfg.HOT_TUB_DEPTH) > 0
    assert to_mm(cfg.HOT_TUB_ABOVE_DECK) > 0
    assert to_mm(cfg.FIREPLACE_WIDTH) > 0
    assert to_mm(cfg.FIREPLACE_DEPTH) > to_mm(cfg.FIREPLACE_WIDTH)
    assert to_mm(cfg.FIREPLACE_HEIGHT) > to_mm(cfg.UPPER_DECK_ELEVATION)
    assert to_mm(cfg.FIREPLACE_OPENING_WIDTH) > 0
    assert to_mm(cfg.FIREPLACE_OPENING_HEIGHT) > 0
    assert to_mm(cfg.TV_WIDTH) > 0
    assert to_mm(cfg.TV_HEIGHT) > 0


def test_kitchen_dimensions(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.KITCHEN_LENGTH) > 0
    assert to_mm(cfg.KITCHEN_DEPTH) > 0
    assert to_mm(cfg.KITCHEN_COUNTER_HEIGHT) > to_mm(cfg.KITCHEN_COUNTER_THICKNESS)
    assert to_mm(cfg.KITCHEN_GRILL_WIDTH) > 0
    assert to_mm(cfg.KITCHEN_DOOR_WIDTH) > 0
    assert to_mm(cfg.KITCHEN_SINK_WIDTH) > 0
    assert to_mm(cfg.KITCHEN_SINK_DEPTH) > 0


def test_sliding_door_and_annotation(copied_project) -> None:
    sys.path.insert(0, str(copied_project))
    try:
        import config as cfg
    finally:
        sys.path.remove(str(copied_project))

    assert to_mm(cfg.DOOR_WIDTH) > 0
    assert to_mm(cfg.DOOR_HEIGHT) > 0
    assert to_mm(cfg.SECTION_CUT_X) >= 0
