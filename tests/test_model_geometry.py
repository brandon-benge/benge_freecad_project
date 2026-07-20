"""Geometry and semantic-metadata contract tests for issues #6 and #9.

Covers:
- 2' tile border ring (individual 2' x 2' tiles, not a solid slab) around the pool
- pool deep end on the reverse (left) side, shallow end on the right
- pool and right tile border extend to the lower deck right edge on the x axis
- grass strip between the lower deck stairs and the pool
- fireplace width doubled (4' wide)
- hot tub deck (lower deck) is 17.5' across
- top (upper) deck extends 20' from the house toward the pool
- stair risers line up with the back of each step (sit on the tread top)

``bounds_mm`` is ``[min_x, min_y, min_z, max_x, max_y, max_z]``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from python_cad_tools.units import FOOT, INCH, to_mm


def _element_by_id(manifest: dict, element_id: str) -> dict:
    for element in manifest["elements"]:
        if element["id"] == element_id:
            return element
    raise AssertionError(f"Element not found in design manifest: {element_id}")


def _bounds(manifest: dict, element_id: str) -> tuple[float, float, float, float, float, float]:
    element = _element_by_id(manifest, element_id)
    bounds = element["bounds_mm"]
    assert len(bounds) == 6, f"Unexpected bounds for {element_id}: {bounds}"
    return tuple(float(v) for v in bounds)  # type: ignore[return-value]


def _load_config(copied_project: Path):
    import sys

    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("config", "model", "drawing_annotations"):
            del sys.modules[mod]
    try:
        import config as cfg

        return cfg
    finally:
        sys.path.remove(str(copied_project))


# ── Pool tile border ring (individual 2' tiles) ─────────────────────────────


TILE_BORDER_PREFIX = "complex.site.pool_tile_border_"


def _tile_ids(manifest: dict) -> set[str]:
    return {e["id"] for e in manifest["elements"] if e["id"].startswith(TILE_BORDER_PREFIX)}


def test_pool_paver_patio_removed(design_manifest: dict) -> None:
    ids = {e["id"] for e in design_manifest["elements"]}
    assert "complex.site.pool_paver_patio" not in ids
    # The four solid border strips from issue #6 are gone; the border is now a
    # ring of individual 2' tiles.
    for old_id in (
        "complex.site.pool_tile_border_left",
        "complex.site.pool_tile_border_right",
        "complex.site.pool_tile_border_near",
        "complex.site.pool_tile_border_far",
    ):
        assert old_id not in ids
    assert _tile_ids(design_manifest), "No individual pool tile border elements found"


def test_pool_tile_border_is_individual_two_foot_tiles(copied_project: Path, design_manifest: dict) -> None:
    cfg = _load_config(copied_project)
    border_mm = to_mm(cfg.PATIO_BORDER)
    tile_mm = to_mm(cfg.POOL_TILE_SIZE)
    assert border_mm == pytest.approx(to_mm(2 * FOOT))
    assert tile_mm == pytest.approx(to_mm(2 * FOOT))

    tile_ids = sorted(_tile_ids(design_manifest))
    # 8 (left) + 8 (right) + 17 (near) + 17 (far) = 50 individual tiles.
    assert len(tile_ids) == 50
    for tile_id in tile_ids:
        b = _bounds(design_manifest, tile_id)
        # Each tile is a 2' x 2' piece (one tile wide in the border direction,
        # 2' long along the run).  The last tile in a run may be shorter if the
        # run length is not a whole multiple of the tile size; here the runs
        # (16' and 34') divide evenly by 2', so every tile is a full 2' x 2'.
        assert (b[3] - b[0]) == pytest.approx(tile_mm), f"{tile_id} x-span != 2'"
        assert (b[4] - b[1]) == pytest.approx(tile_mm), f"{tile_id} y-span != 2'"


def test_pool_tile_border_ring_surrounds_pool_without_overlap(design_manifest: dict) -> None:
    pool = _bounds(design_manifest, "complex.pool.pool_water_34x12_5ft_to8ft")
    pool_min_x, pool_min_y, _, pool_max_x, pool_max_y, _ = pool

    for tile_id in sorted(_tile_ids(design_manifest)):
        b = _bounds(design_manifest, tile_id)
        # No tile overlaps the pool footprint in plan (x/y).
        outside_x = b[3] <= pool_min_x + 1e-6 or b[0] >= pool_max_x - 1e-6
        outside_y = b[4] <= pool_min_y + 1e-6 or b[1] >= pool_max_y - 1e-6
        assert outside_x or outside_y, f"Tile {tile_id} overlaps the pool footprint"


def test_pool_tile_border_no_tile_overlaps_another(design_manifest: dict) -> None:
    tile_bounds = [(_bounds(design_manifest, tile_id), tile_id) for tile_id in sorted(_tile_ids(design_manifest))]
    for i, (a, id_a) in enumerate(tile_bounds):
        for b, id_b in tile_bounds[i + 1 :]:
            overlap_x = a[0] < b[3] - 1e-6 and b[0] < a[3] - 1e-6
            overlap_y = a[1] < b[4] - 1e-6 and b[1] < a[4] - 1e-6
            assert not (overlap_x and overlap_y), f"Tiles overlap: {id_a} and {id_b}"


def test_pool_tile_material_registered(design_manifest: dict) -> None:
    tile_elements = [e for e in design_manifest["elements"] if e["id"].startswith(TILE_BORDER_PREFIX)]
    assert len(tile_elements) == 50
    for element in tile_elements:
        assert element["material_id"] == "material.complex.site.199_204_209"
    # No paver-colored site element remains.
    assert not any(e["material_id"] == "material.complex.site.178_178_173" for e in design_manifest["elements"])


# ── Pool deep end on the reverse (left) side ─────────────────────────────────


def test_pool_deep_end_on_reverse_side(copied_project: Path, design_manifest: dict) -> None:
    cfg = _load_config(copied_project)
    assert cfg.POOL_DEEP_END_SIDE == "left"

    pool = _bounds(design_manifest, "complex.pool.pool_water_34x12_5ft_to8ft")
    pool_min_x, _, pool_min_z, pool_max_x, _, pool_max_z = pool
    # The pool reaches the full deep depth on the reverse (left) side.
    assert pool_min_z == pytest.approx(-to_mm(cfg.POOL_DEEP_DEPTH))
    assert pool_max_z == pytest.approx(0.0)

    # Verify the deep end is on the left by inspecting the pool solid's
    # vertices: the deepest (min z) vertices must sit at the left (min x) edge.
    import sys

    from python_cad_tools.context import BuildContext
    from python_cad_tools.units import mm

    sys.path.insert(0, str(copied_project))
    for mod in list(sys.modules):
        if mod in ("config", "model", "drawing_annotations"):
            del sys.modules[mod]
    try:
        import model as model_mod

        ctx = BuildContext(project_root=copied_project, config=cfg, source_revision="test", source_dirty=False)
        design = model_mod.build_model(ctx)
    finally:
        sys.path.remove(str(copied_project))

    pool_element = next(e for e in design.elements if e.id == "complex.pool.pool_water_34x12_5ft_to8ft")
    vertices = list(pool_element.geometry.vertices())
    deep_z = min(v.Z for v in vertices)
    shallow_z = max(v.Z for v in vertices if v.Z < 0.0)
    # Deepest vertices are at the deep depth.
    assert deep_z == pytest.approx(-to_mm(cfg.POOL_DEEP_DEPTH))
    # The shallow-bottom vertices are at the shallow depth.
    assert shallow_z == pytest.approx(-to_mm(cfg.POOL_SHALLOW_DEPTH))
    # Every deepest vertex is at the left (min x) edge of the pool.
    for v in vertices:
        if abs(v.Z - deep_z) < 1e-3:
            assert pytest.approx(pool_min_x) == v.X, f"Deep vertex not on left edge: x={v.X}"
    # Every shallow-bottom vertex is at the right (max x) edge of the pool.
    for v in vertices:
        if abs(v.Z - shallow_z) < 1e-3:
            assert pytest.approx(pool_max_x) == v.X, f"Shallow vertex not on right edge: x={v.X}"
    # Silence unused import warnings for mm (kept for future geometry assertions).
    assert mm is not None


# ── Pool and right tile border extend to the lower deck right edge ────────────


def test_pool_and_right_border_extend_to_lower_deck_edge(copied_project: Path, design_manifest: dict) -> None:
    cfg = _load_config(copied_project)
    lower_deck_right_x = to_mm(cfg.UPPER_DECK_WIDTH + cfg.LOWER_DECK_WIDTH)

    pool = _bounds(design_manifest, "complex.pool.pool_water_34x12_5ft_to8ft")
    # The pool sits just inside the right tile border, so its right edge is one
    # border width short of the lower deck right edge.
    assert pool[3] == pytest.approx(lower_deck_right_x - to_mm(cfg.PATIO_BORDER))

    # The rightmost tile border tile's right edge aligns with the lower deck
    # right edge.
    right_tile_ids = sorted(
        e["id"] for e in design_manifest["elements"] if e["id"].startswith("complex.site.pool_tile_border_right_")
    )
    assert right_tile_ids, "No right tile border tiles found"
    rightmost = max((_bounds(design_manifest, tid) for tid in right_tile_ids), key=lambda b: b[3])
    assert rightmost[3] == pytest.approx(lower_deck_right_x)


# ── Grass between the deck and the pool ──────────────────────────────────────


def test_grass_strip_between_deck_and_pool(copied_project: Path, design_manifest: dict) -> None:
    cfg = _load_config(copied_project)
    grass = _bounds(design_manifest, "complex.site.pool_grass_strip")
    pool = _bounds(design_manifest, "complex.pool.pool_water_34x12_5ft_to8ft")

    # Grass sits between the lower deck stairs and the pool's near tile border.
    # Use config-derived stair end: lower deck front + 55 inches.
    stair_end_y = -to_mm(cfg.LOWER_DECK_DEPTH) - to_mm(55 * INCH)
    # Grass near edge (toward deck) is at the stair end.
    assert grass[4] == pytest.approx(stair_end_y)
    # Grass far edge (toward pool) is at the pool near tile border's near edge.
    pool_near_border_edge = pool[4] + to_mm(cfg.PATIO_BORDER)
    assert grass[1] == pytest.approx(pool_near_border_edge)
    # Grass is on the deck side of the pool (no overlap with pool footprint).
    assert grass[1] >= pool[4] - 1e-6


# ── Fireplace width doubled to 4' ────────────────────────────────────────────


def test_fireplace_width_doubled(copied_project: Path, design_manifest: dict) -> None:
    cfg = _load_config(copied_project)
    assert to_mm(cfg.FIREPLACE_WIDTH) == pytest.approx(to_mm(4 * FOOT))
    fireplace = _bounds(design_manifest, "complex.fireplace.fireplace_masonry_body")
    assert (fireplace[3] - fireplace[0]) == pytest.approx(to_mm(4 * FOOT))


# ── Hot tub deck (lower deck) is 17.5' across ───────────────────────────────


def test_lower_deck_width_seventeen_and_a_half_feet(copied_project: Path) -> None:
    cfg = _load_config(copied_project)
    assert to_mm(cfg.LOWER_DECK_WIDTH) == pytest.approx(to_mm(17.5 * FOOT))


def test_hot_tub_sits_within_lower_deck(design_manifest: dict) -> None:
    hot_tub = _bounds(design_manifest, "complex.feature.hot_tub_placeholder")
    lower_skirt = _bounds(design_manifest, "complex.skirting.lower_deck_right_skirt")
    # Lower deck right edge is the right skirt's left x (min_x).
    lower_right_x = lower_skirt[0]
    # Hot tub must fit within the lower deck footprint.
    assert hot_tub[3] <= lower_right_x + 1e-6
    assert hot_tub[0] >= 0.0  # right of the upper deck
    # Hot tub is at least 1' clear from the lower deck right edge.
    assert (lower_right_x - hot_tub[3]) >= to_mm(1 * FOOT) - 1e-6


# ── Top (upper) deck extends 20' from the house toward the pool ──────────────


def test_upper_deck_depth_twenty_feet(copied_project: Path) -> None:
    cfg = _load_config(copied_project)
    assert to_mm(cfg.UPPER_DECK_DEPTH) == pytest.approx(to_mm(20 * FOOT))


def test_upper_deck_front_skirt_at_twenty_feet(copied_project: Path, design_manifest: dict) -> None:
    cfg = _load_config(copied_project)
    skirt = _bounds(design_manifest, "complex.skirting.upper_deck_front_skirt")
    # Front skirt near edge (max_y) sits at y = -UPPER_DECK_DEPTH (20' from house).
    assert skirt[4] == pytest.approx(-to_mm(cfg.UPPER_DECK_DEPTH))
    assert skirt[4] == pytest.approx(-to_mm(20 * FOOT))


# ── Stair risers line up with the back of the step ───────────────────────────


@pytest.mark.parametrize(
    "prefix, count",
    [
        ("upper_straight", 4),
        ("lower_front", 5),
    ],
)
def test_risers_sit_on_tread_top(design_manifest: dict, prefix: str, count: int) -> None:
    for index in range(1, count + 1):
        tread = _bounds(design_manifest, f"complex.stair.{prefix}_tread_{index:02d}")
        riser = _bounds(design_manifest, f"complex.stair.{prefix}_riser_{index:02d}")
        tread_top_z = tread[5]  # max_z
        riser_bottom_z = riser[2]  # min_z
        # Riser bottom must equal tread top (sits on the tread, not through it).
        assert riser_bottom_z == pytest.approx(tread_top_z), (
            f"{prefix} step {index}: riser bottom {riser_bottom_z} != tread top {tread_top_z}"
        )


@pytest.mark.parametrize(
    "prefix, count",
    [
        ("upper_straight", 4),
        ("lower_front", 5),
    ],
)
def test_riser_at_back_of_tread(design_manifest: dict, prefix: str, count: int) -> None:
    for index in range(1, count + 1):
        tread = _bounds(design_manifest, f"complex.stair.{prefix}_tread_{index:02d}")
        riser = _bounds(design_manifest, f"complex.stair.{prefix}_riser_{index:02d}")
        # The riser's back face must align with the tread's back edge.  Because
        # the stair runs along -y, the "back" (toward the upper landing) is the
        # larger y value (max_y, index 4) of each element.
        tread_back_y = tread[4]
        riser_back_y = riser[4]
        assert riser_back_y == pytest.approx(tread_back_y), (
            f"{prefix} step {index}: riser back {riser_back_y} != tread back {tread_back_y}"
        )
