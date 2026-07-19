"""Model-level geometry and semantic checks for the issue-4 design changes.

Covers:
  1. 3' tile ground layer around the pool (replaces the single PoolPaverPatio slab).
  2. Hot tub deck 17.5' across with the 8'x8' hot tub centered on it.
  3. Top deck extends 20' from the house towards the pool.
"""

from __future__ import annotations

import sys
from pathlib import Path

from python_cad_tools.elements import DesignElement
from python_cad_tools.units import to_mm


def _load_config(copied_project: Path):
    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("config", "model"):
            del sys.modules[mod]
    try:
        import config as cfg

        return cfg
    finally:
        sys.path.remove(str(copied_project))


def _elements_by_id(model) -> dict[str, DesignElement]:
    return {element.id: element for element in model.elements}


# ── 1. Pool tile border ring ─────────────────────────────────────────────────


def test_pool_paver_patio_removed(model_from_project) -> None:
    ids = _elements_by_id(model_from_project)
    assert "complex.site.pool_paver_patio" not in ids


def test_pool_tile_border_strips_present(model_from_project) -> None:
    ids = _elements_by_id(model_from_project)
    for name in ("north", "south", "east", "west"):
        assert f"complex.site.pool_tile_border_{name}" in ids


def test_pool_tile_border_dimensions(model_from_project, copied_project) -> None:
    cfg = _load_config(copied_project)
    ids = _elements_by_id(model_from_project)
    border_mm = to_mm(cfg.POOL_TILE_BORDER)
    thickness_mm = to_mm(cfg.POOL_TILE_THICKNESS)
    pool_length_mm = to_mm(cfg.POOL_LENGTH)
    pool_width_mm = to_mm(cfg.POOL_WIDTH)
    span_x = pool_length_mm + 2 * border_mm

    north = ids["complex.site.pool_tile_border_north"]
    south = ids["complex.site.pool_tile_border_south"]
    east = ids["complex.site.pool_tile_border_east"]
    west = ids["complex.site.pool_tile_border_west"]

    assert north.dimensions.length_mm == span_x
    assert north.dimensions.width_mm == border_mm
    assert north.dimensions.height_mm == thickness_mm
    assert south.dimensions.length_mm == span_x
    assert south.dimensions.width_mm == border_mm
    assert south.dimensions.height_mm == thickness_mm
    assert east.dimensions.length_mm == border_mm
    assert east.dimensions.width_mm == pool_width_mm
    assert east.dimensions.height_mm == thickness_mm
    assert west.dimensions.length_mm == border_mm
    assert west.dimensions.width_mm == pool_width_mm
    assert west.dimensions.height_mm == thickness_mm


def test_pool_tile_border_ring_encloses_pool_and_does_not_overlap(model_from_project, copied_project) -> None:
    cfg = _load_config(copied_project)
    ids = _elements_by_id(model_from_project)
    border_mm = to_mm(cfg.POOL_TILE_BORDER)
    pool_length_mm = to_mm(cfg.POOL_LENGTH)
    pool_width_mm = to_mm(cfg.POOL_WIDTH)

    pool = ids["complex.pool.pool_water_34x12_5ft_to8ft"]
    pool_x = pool.placement.translation_mm[0]
    pool_y = pool.placement.translation_mm[1]
    pool_x_min, pool_x_max = pool_x, pool_x + pool_length_mm
    pool_y_min, pool_y_max = pool_y, pool_y + pool_width_mm

    expected_ring_x_min = pool_x_min - border_mm
    expected_ring_x_max = pool_x_max + border_mm
    expected_ring_y_min = pool_y_min - border_mm
    expected_ring_y_max = pool_y_max + border_mm

    strips = {
        "north": ids["complex.site.pool_tile_border_north"],
        "south": ids["complex.site.pool_tile_border_south"],
        "east": ids["complex.site.pool_tile_border_east"],
        "west": ids["complex.site.pool_tile_border_west"],
    }

    def footprint(element) -> tuple[float, float, float, float]:
        x = element.placement.translation_mm[0]
        y = element.placement.translation_mm[1]
        length = element.dimensions.length_mm or 0.0
        width = element.dimensions.width_mm or 0.0
        return x, y, x + length, y + width

    # Union of strip footprints must equal the full ring bounds.
    union_x_min = min(fp[0] for fp in (footprint(s) for s in strips.values()))
    union_y_min = min(fp[1] for fp in (footprint(s) for s in strips.values()))
    union_x_max = max(fp[2] for fp in (footprint(s) for s in strips.values()))
    union_y_max = max(fp[3] for fp in (footprint(s) for s in strips.values()))
    assert union_x_min == expected_ring_x_min
    assert union_y_min == expected_ring_y_min
    assert union_x_max == expected_ring_x_max
    assert union_y_max == expected_ring_y_max

    # No strip footprint may overlap the pool footprint.
    for name, strip in strips.items():
        sx_min, sy_min, sx_max, sy_max = footprint(strip)
        overlaps = not (sx_max <= pool_x_min or sx_min >= pool_x_max or sy_max <= pool_y_min or sy_min >= pool_y_max)
        assert not overlaps, f"{name} strip overlaps the pool footprint"

    # Strips must be mutually non-overlapping.
    names = list(strips)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = footprint(strips[names[i]])
            b = footprint(strips[names[j]])
            overlap = not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])
            assert not overlap, f"{names[i]} overlaps {names[j]}"


def test_pool_tile_material_replaces_pavers(model_from_project) -> None:
    ids = _elements_by_id(model_from_project)
    tile = ids["complex.site.pool_tile_border_north"]
    assert tile.material is not None
    assert tile.material.name == "Pool Deck Tile"


# ── 2. Hot tub deck 17.5' across ─────────────────────────────────────────────


def test_hot_tub_platform_dimensions(model_from_project, copied_project) -> None:
    cfg = _load_config(copied_project)
    ids = _elements_by_id(model_from_project)
    platform = ids["complex.structure.hot_tub_platform"]
    assert platform.dimensions.length_mm == to_mm(cfg.HOT_TUB_DECK_WIDTH)
    assert platform.dimensions.width_mm == to_mm(cfg.HOT_TUB_DECK_DEPTH)
    assert platform.dimensions.extras["deck_width_mm"] == to_mm(cfg.HOT_TUB_DECK_WIDTH)
    assert platform.dimensions.extras["deck_depth_mm"] == to_mm(cfg.HOT_TUB_DECK_DEPTH)


def test_hot_tub_placeholder_centered_on_deck(model_from_project, copied_project) -> None:
    cfg = _load_config(copied_project)
    ids = _elements_by_id(model_from_project)
    platform = ids["complex.structure.hot_tub_platform"]
    placeholder = ids["complex.feature.hot_tub_placeholder"]

    deck_x = platform.placement.translation_mm[0]
    deck_y = platform.placement.translation_mm[1]
    deck_w = platform.dimensions.length_mm or 0.0
    deck_d = platform.dimensions.width_mm or 0.0

    ph_x = placeholder.placement.translation_mm[0]
    ph_y = placeholder.placement.translation_mm[1]
    ph_w = placeholder.dimensions.length_mm or 0.0
    ph_d = placeholder.dimensions.width_mm or 0.0

    assert ph_w == to_mm(cfg.HOT_TUB_WIDTH)
    assert ph_d == to_mm(cfg.HOT_TUB_DEPTH)

    assert ph_x == deck_x + (deck_w - ph_w) / 2
    assert ph_y == deck_y + (deck_d - ph_d) / 2


# ── 3. Top deck extends 20' from the house ────────────────────────────────────


def test_upper_deck_depth_is_20_feet(model_from_project, copied_project) -> None:
    cfg = _load_config(copied_project)
    ids = _elements_by_id(model_from_project)
    # UpperDeckLeftSkirt spans the upper deck depth along Y (its width_mm).
    skirt = ids["complex.skirting.upper_deck_left_skirt"]
    assert skirt.dimensions.width_mm == to_mm(cfg.UPPER_DECK_DEPTH)
    assert to_mm(cfg.UPPER_DECK_DEPTH) == to_mm(20 * cfg.FOOT)


def test_upper_deck_board_run_matches_20_foot_depth(model_from_project) -> None:
    upper_boards = [
        element
        for element in model_from_project.elements
        if element.category == "deck-board" and element.name.startswith("UpperDeckBoard_")
    ]
    assert upper_boards, "Expected upper deck boards"
    # Boards run along X (direction "x"); each board's width_mm is its Y span.
    # 20' = 6096mm; with 5.5" + 0.25" pitch (146.05mm), expect 42 boards with
    # the final board clipped so the trailing edge lands exactly at 6096mm.
    assert len(upper_boards) == 42
    leading_edges = [board.placement.translation_mm[1] for board in upper_boards]
    trailing_edges = [board.placement.translation_mm[1] + (board.dimensions.width_mm or 0.0) for board in upper_boards]
    # Deck spans y in [-UPPER_DECK_DEPTH, 0]; board run must cover exactly 6096mm.
    assert round(min(leading_edges), 3) == -6096.0
    assert round(max(trailing_edges), 3) == 0.0
    assert round(max(trailing_edges) - min(leading_edges), 3) == 6096.0
