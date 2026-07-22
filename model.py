"""Headless shared-model translation of the linked File Template CAD concept."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from build123d import Cone, Plane, Polyline, Sphere, extrude, make_face
from python_cad_tools.context import BuildContext
from python_cad_tools.elements import DesignElement, DesignModel, Dimensions, IfcMapping, MaterialSpec, Placement
from python_cad_tools.geometry import box, cylinder_between, prism_between, sloped_pool
from python_cad_tools.units import FOOT, INCH, MM, Length, mm, to_mm

import config as cfg

ZERO = 0 * MM
Color = tuple[float, float, float]
Point3 = tuple[Length, Length, Length]
Point2 = tuple[Length, Length]

TREE_GREEN: Color = (0.0, 0.45, 0.15)
TREE_BROWN: Color = (0.40, 0.25, 0.10)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()).strip("_")


# Human-readable material names and densities (kg/m³) keyed by (category, color_rgb).
# Each entry: human_readable_name, density_kg_m3
# Material IDs (generated from category + rounded RGB) remain stable for backward compatibility.
MATERIAL_REGISTRY: dict[tuple[str, Color], tuple[str, float | None]] = {
    # Deck
    ("deck-board", cfg.DECK_COLOR): ("Composite Decking", 700.0),
    ("deck-framing", cfg.SKIRTING_COLOR): ("Pressure-Treated Lumber", 500.0),
    ("deck-framing", cfg.RAILING_COLOR): ("Pressure-Treated Lumber", 500.0),
    # Roof
    ("roof", cfg.RAILING_COLOR): ("Roof Fascia Assembly", 500.0),
    ("roof", (0.18, 0.20, 0.22)): ("Roof Cover Assembly", 50.0),
    ("roof-framing", (0.92, 0.92, 0.90)): ("Dimensional Lumber", 500.0),
    ("roof-framing", cfg.RAILING_COLOR): ("Roof Beam Assembly", 500.0),
    # Features
    ("feature", (0.55, 0.70, 0.82)): ("Glass Door Assembly", 2500.0),
    ("feature", (0.08, 0.10, 0.12)): ("Hot Tub Shell", 150.0),
    ("feature", cfg.RAILING_COLOR): ("Ceiling Fan Assembly", 500.0),
    ("feature", cfg.SKIRTING_COLOR): ("Fan Blade (Wood)", 600.0),
    # Fireplace
    ("fireplace", cfg.BRICK_COLOR): ("Brick Masonry", 2000.0),
    ("fireplace", (0.90, 0.28, 0.08)): ("Electric Fireplace Insert", 500.0),
    ("fireplace", (0.02, 0.02, 0.025)): ("Flat Screen TV", 300.0),
    ("fireplace", (0.03, 0.03, 0.03)): ("Fireplace Opening (Void)", 100.0),
    ("fireplace", (0.10, 0.10, 0.10)): ("Metal Chimney Cap", 500.0),
    ("fireplace", (0.02, 0.02, 0.02)): ("Chimney Flue Opening", 100.0),
    # Skirting access panels
    ("skirting", (0.30, 0.25, 0.20)): ("Access Panel (Wood)", 600.0),
    # House
    ("house", cfg.HOUSE_COLOR): ("Mixed Wall Assembly", 300.0),
    # Outdoor kitchen
    ("outdoor-kitchen", (0.45, 0.45, 0.42)): ("Granite Countertop", 2400.0),
    ("outdoor-kitchen", (0.05, 0.05, 0.05)): ("Stainless Steel Grill", 2700.0),
    ("outdoor-kitchen", (0.75, 0.75, 0.72)): ("Chrome Faucet", 2700.0),
    ("outdoor-kitchen", (0.12, 0.12, 0.12)): ("Cabinet Box (Wood)", 600.0),
    ("outdoor-kitchen", (0.12, 0.15, 0.16)): ("Stainless Steel Sink", 2700.0),
    ("outdoor-kitchen", (0.22, 0.22, 0.22)): ("Cabinet Door (Wood)", 600.0),
    # Pool
    ("pool", cfg.WATER_COLOR): ("Water", 1000.0),
    # Railing
    ("railing", cfg.RAILING_COLOR): ("Wood/Metal Railing", 500.0),
    # Site
    ("site", cfg.PAVER_COLOR): ("Concrete Pavers", 2400.0),
    ("site", cfg.TILE_COLOR): ("Pool Tile", 2300.0),
    ("site", cfg.GRASS_COLOR): ("Turf Grass", 50.0),
    ("site", cfg.ROCK_COLOR): ("Landscape Rock", 1650.0),
    ("site", cfg.FENCE_COLOR): ("Black Powder-Coated Aluminum Fence", 2700.0),
    # Vegetation solids are visual landscaping proxies, not material takeoff
    # solids; an unspecified density prevents fabricated construction mass.
    ("site", TREE_GREEN): ("Evergreen Tree (Conceptual)", None),
    ("site", TREE_BROWN): ("Tree Trunk (Conceptual)", None),
    # Yard storage shed
    ("shed", cfg.SHED_SIDING_COLOR): ("Painted Wood Siding", 550.0),
    ("shed", cfg.SHED_TRIM_COLOR): ("Painted Wood Trim", 550.0),
    ("shed", cfg.SHED_ROOF_COLOR): ("Asphalt Shingle Roof", 50.0),
    ("shed", (0.15, 0.15, 0.15)): ("Concrete Shed Slab", 2400.0),
    # Skirting
    ("skirting", cfg.SKIRTING_COLOR): ("Pressure-Treated Skirting", 500.0),
    ("skirting", (0.95, 0.85, 0.10)): ("Low-Voltage LED Deck Light", 100.0),
    # Stair
    ("stair", cfg.DECK_COLOR): ("Composite Tread", 700.0),
    ("stair", cfg.SKIRTING_COLOR): ("Framing Lumber", 500.0),
    ("stair", (0.95, 0.85, 0.10)): ("LED Step Light", 100.0),
    # Structure
    ("structure", (0.15, 0.15, 0.15)): ("Concrete Slab", 2400.0),
}


@dataclass
class ModelBuilder:
    elements: list[DesignElement] = field(default_factory=list)
    materials: dict[tuple[str, Color], MaterialSpec] = field(default_factory=dict)

    def material(self, category: str, color: Color) -> MaterialSpec:
        key = (category, color)
        if key not in self.materials:
            rgb = "_".join(str(round(channel * 255)) for channel in color)
            info = MATERIAL_REGISTRY.get(key)
            name = info[0] if info else f"{category.title()} material"
            density = info[1] if info else None
            self.materials[key] = MaterialSpec(
                id=f"material.complex.{_slug(category)}.{rgb}",
                name=name,
                category=category,
                color_rgb=color,
                density_kg_m3=density,
            )
        return self.materials[key]

    def add_shape(
        self,
        category: str,
        name: str,
        shape: Any,
        color: Color,
        dimensions: Dimensions,
        *,
        placement: Point3 = (ZERO, ZERO, ZERO),
        drawing_label: bool = False,
        properties: dict[str, Any] | None = None,
        physical: bool = True,
        parent_id: str | None = None,
        export_formats: set[str] | None = None,
        stable_id: str | None = None,
        ifc_mapping: IfcMapping | None = None,
    ) -> DesignElement:
        resolved_stable_id = stable_id or f"complex.{_slug(category)}.{_slug(name)}"
        values = dict(properties or {})
        if drawing_label:
            values["drawing_label"] = True
        element = DesignElement(
            id=resolved_stable_id,
            name=name,
            category=category,
            geometry=shape,
            geometry_kind="solid",
            placement=Placement((to_mm(placement[0]), to_mm(placement[1]), to_mm(placement[2]))),
            dimensions=dimensions,
            material=self.material(category, color),
            color_rgb=color,
            ifc_mapping=ifc_mapping or IfcMapping("IfcBuildingElementProxy", "NOTDEFINED"),
            storey="Exterior Concept",
            tags={"file-template", _slug(category)},
            properties=values,
            source_module="model",
            physical=physical,
            parent_id=parent_id,
            export_formats=set(export_formats or {"step", "ifc", "glb", "drawings", "quantities"}),
        )
        self.elements.append(element)
        return element

    def add_box(
        self,
        category: str,
        name: str,
        length: Length,
        depth: Length,
        height: Length,
        x: Length,
        y: Length,
        z: Length,
        color: Color,
        *,
        drawing_label: bool = False,
        properties: dict[str, Any] | None = None,
        physical: bool = True,
        parent_id: str | None = None,
        export_formats: set[str] | None = None,
        stable_id: str | None = None,
        ifc_mapping: IfcMapping | None = None,
    ) -> DesignElement:
        return self.add_shape(
            category,
            name,
            box(length, depth, height, origin=(x, y, z)),
            color,
            Dimensions(to_mm(length), to_mm(depth), to_mm(height)),
            placement=(x, y, z),
            drawing_label=drawing_label,
            properties=properties,
            physical=physical,
            parent_id=parent_id,
            export_formats=export_formats,
            stable_id=stable_id,
            ifc_mapping=ifc_mapping,
        )

    def add_cylinder(
        self,
        category: str,
        name: str,
        start: Point3,
        end: Point3,
        radius: Length,
        color: Color,
        *,
        physical: bool = True,
        parent_id: str | None = None,
        properties: dict[str, Any] | None = None,
        export_formats: set[str] | None = None,
    ) -> DesignElement:
        length = math.dist(tuple(to_mm(value) for value in start), tuple(to_mm(value) for value in end))
        return self.add_shape(
            category,
            name,
            cylinder_between(start, end, radius),
            color,
            Dimensions(length_mm=length, radius_mm=to_mm(radius)),
            placement=start,
            physical=physical,
            parent_id=parent_id,
            properties=properties,
            export_formats=export_formats,
        )

    def add_prism(
        self,
        category: str,
        name: str,
        start: Point3,
        end: Point3,
        width: Length,
        height: Length,
        color: Color,
        *,
        physical: bool = True,
        parent_id: str | None = None,
        properties: dict[str, Any] | None = None,
        export_formats: set[str] | None = None,
    ) -> DesignElement:
        length = math.dist(tuple(to_mm(value) for value in start), tuple(to_mm(value) for value in end))
        return self.add_shape(
            category,
            name,
            prism_between(start, end, width, height),
            color,
            Dimensions(length, to_mm(width), to_mm(height)),
            placement=start,
            physical=physical,
            parent_id=parent_id,
            properties=properties,
            export_formats=export_formats,
        )


def build_model(context: BuildContext) -> DesignModel:
    builder = ModelBuilder()

    def add_deck_boards(
        prefix: str, x: Length, y: Length, length: Length, depth: Length, z: Length, direction: str
    ) -> None:
        board_z = z - cfg.DECK_BOARD_THICKNESS
        pitch = cfg.DECK_BOARD_WIDTH + cfg.DECK_BOARD_GAP
        index = 1
        if direction == "x":
            board_y = y
            while board_y < y + depth:
                board_depth = min(cfg.DECK_BOARD_WIDTH, y + depth - board_y)
                builder.add_box(
                    "deck-board",
                    f"{prefix}DeckBoard_{index:02d}",
                    length,
                    board_depth,
                    cfg.DECK_BOARD_THICKNESS,
                    x,
                    board_y,
                    board_z,
                    cfg.DECK_COLOR,
                )
                board_y = board_y + pitch
                index += 1
        else:
            board_x = x
            while board_x < x + length:
                board_length = min(cfg.DECK_BOARD_WIDTH, x + length - board_x)
                builder.add_box(
                    "deck-board",
                    f"{prefix}DeckBoard_{index:02d}",
                    board_length,
                    depth,
                    cfg.DECK_BOARD_THICKNESS,
                    board_x,
                    y,
                    board_z,
                    cfg.DECK_COLOR,
                )
                board_x = board_x + pitch
                index += 1

    def add_deck_framing(
        prefix: str,
        x: Length,
        y: Length,
        length: Length,
        depth: Length,
        z: Length,
        post_points: list[Point2],
        *,
        mid_beam_y: Length | None = None,
        mid_beam_properties: dict[str, Any] | None = None,
    ) -> None:
        frame_top = z - cfg.DECK_BOARD_THICKNESS
        joist_z = frame_top - cfg.JOIST_HEIGHT
        beam_z = joist_z - cfg.BEAM_HEIGHT
        builder.add_box(
            "deck-framing",
            f"{prefix}FrontRimJoist",
            length,
            cfg.JOIST_WIDTH,
            cfg.JOIST_HEIGHT,
            x,
            y,
            joist_z,
            cfg.SKIRTING_COLOR,
        )
        builder.add_box(
            "deck-framing",
            f"{prefix}BackLedger",
            length,
            cfg.JOIST_WIDTH,
            cfg.JOIST_HEIGHT,
            x,
            y + depth - cfg.JOIST_WIDTH,
            joist_z,
            cfg.SKIRTING_COLOR,
        )
        builder.add_box(
            "deck-framing",
            f"{prefix}LeftRimJoist",
            cfg.JOIST_WIDTH,
            depth,
            cfg.JOIST_HEIGHT,
            x,
            y,
            joist_z,
            cfg.SKIRTING_COLOR,
        )
        builder.add_box(
            "deck-framing",
            f"{prefix}RightRimJoist",
            cfg.JOIST_WIDTH,
            depth,
            cfg.JOIST_HEIGHT,
            x + length - cfg.JOIST_WIDTH,
            y,
            joist_z,
            cfg.SKIRTING_COLOR,
        )
        joist_x = x + cfg.JOIST_SPACING
        joist_index = 1
        while joist_x < x + length - cfg.JOIST_WIDTH:
            builder.add_box(
                "deck-framing",
                f"{prefix}Joist_{joist_index:02d}",
                cfg.JOIST_WIDTH,
                depth,
                cfg.JOIST_HEIGHT,
                joist_x,
                y,
                joist_z,
                cfg.SKIRTING_COLOR,
            )
            joist_x = joist_x + cfg.JOIST_SPACING
            joist_index += 1
        builder.add_box(
            "deck-framing",
            f"{prefix}FrontBeam",
            length,
            cfg.BEAM_WIDTH,
            cfg.BEAM_HEIGHT,
            x,
            y - cfg.BEAM_WIDTH,
            beam_z,
            cfg.RAILING_COLOR,
        )
        if depth > 8 * cfg.FOOT:
            resolved_mid_beam_y = mid_beam_y if mid_beam_y is not None else y + depth / 2 - cfg.BEAM_WIDTH / 2
            builder.add_box(
                "deck-framing",
                f"{prefix}MidBeam",
                length,
                cfg.BEAM_WIDTH,
                cfg.BEAM_HEIGHT,
                x,
                resolved_mid_beam_y,
                beam_z,
                cfg.RAILING_COLOR,
                properties=mid_beam_properties,
            )
        for index, (post_x, post_y) in enumerate(post_points, 1):
            builder.add_box(
                "deck-framing",
                f"{prefix}SupportPost_{index:02d}",
                cfg.SUPPORT_POST_SIZE,
                cfg.SUPPORT_POST_SIZE,
                beam_z,
                post_x - cfg.SUPPORT_POST_SIZE / 2,
                post_y - cfg.SUPPORT_POST_SIZE / 2,
                ZERO,
                cfg.RAILING_COLOR,
            )

    sliding_door_x = 3 * cfg.FOOT + 6 * INCH
    sliding_door_y = -1.5 * INCH
    house_mass = box(cfg.HOUSE_WIDTH, cfg.HOUSE_DEPTH, cfg.HOUSE_HEIGHT, origin=(ZERO, ZERO, ZERO))
    sliding_door_opening = box(
        cfg.DOOR_WIDTH,
        cfg.HOUSE_DEPTH,
        cfg.DOOR_HEIGHT,
        origin=(sliding_door_x, ZERO, cfg.UPPER_DECK_ELEVATION),
    )
    builder.add_shape(
        "house",
        "HouseMass",
        house_mass.cut(sliding_door_opening),
        cfg.HOUSE_COLOR,
        Dimensions(to_mm(cfg.HOUSE_WIDTH), to_mm(cfg.HOUSE_DEPTH), to_mm(cfg.HOUSE_HEIGHT)),
        drawing_label=True,
        properties={
            "complex_type": "house_mass",
            "assembly_role": "exterior_wall_with_openings",
            "opening_for": "complex.feature.sliding_door",
        },
    )
    add_deck_boards(
        "Upper", ZERO, -cfg.UPPER_DECK_DEPTH, cfg.UPPER_DECK_WIDTH, cfg.UPPER_DECK_DEPTH, cfg.UPPER_DECK_ELEVATION, "x"
    )
    add_deck_framing(
        "Upper",
        ZERO,
        -cfg.UPPER_DECK_DEPTH,
        cfg.UPPER_DECK_WIDTH,
        cfg.UPPER_DECK_DEPTH,
        cfg.UPPER_DECK_ELEVATION,
        [
            (ZERO, -cfg.UPPER_DECK_DEPTH),
            (cfg.UPPER_DECK_WIDTH / 2, -cfg.UPPER_DECK_DEPTH),
            (cfg.UPPER_DECK_WIDTH, -cfg.UPPER_DECK_DEPTH),
            (ZERO, -cfg.UPPER_DECK_DEPTH / 2),
            (cfg.UPPER_DECK_WIDTH, -cfg.UPPER_DECK_DEPTH / 2),
        ],
        mid_beam_properties={
            "complex_type": "deck_support_beam",
            "assembly_role": "mid_span_support",
            "supports": "complex.deck_board.upper_*",
            "clear_of": "complex.skirting.upper_deck_left_skirt_access_panel",
        },
    )

    lower_x = cfg.UPPER_DECK_WIDTH
    hot_tub_x = cfg.UPPER_DECK_WIDTH + cfg.LOWER_DECK_WIDTH - cfg.HOT_TUB_WIDTH - cfg.FOOT
    hot_tub_y = -(cfg.HOT_TUB_DEPTH + 1.5 * cfg.FOOT)
    lower_mid_beam_y = hot_tub_y - cfg.BEAM_FEATURE_CLEARANCE - cfg.BEAM_WIDTH
    add_deck_boards(
        "Lower",
        lower_x,
        -cfg.LOWER_DECK_DEPTH,
        cfg.LOWER_DECK_WIDTH,
        cfg.LOWER_DECK_DEPTH,
        cfg.LOWER_DECK_ELEVATION,
        "y",
    )
    add_deck_framing(
        "Lower",
        lower_x,
        -cfg.LOWER_DECK_DEPTH,
        cfg.LOWER_DECK_WIDTH,
        cfg.LOWER_DECK_DEPTH,
        cfg.LOWER_DECK_ELEVATION,
        [
            (lower_x, -cfg.LOWER_DECK_DEPTH),
            (lower_x + cfg.LOWER_DECK_WIDTH / 2, -cfg.LOWER_DECK_DEPTH),
            (lower_x + cfg.LOWER_DECK_WIDTH, -cfg.LOWER_DECK_DEPTH),
            (lower_x + cfg.LOWER_DECK_WIDTH, lower_mid_beam_y + cfg.BEAM_WIDTH / 2),
        ],
        mid_beam_y=lower_mid_beam_y,
        mid_beam_properties={
            "complex_type": "deck_support_beam",
            "assembly_role": "mid_span_support",
            "supports": "complex.deck_board.lower_*",
            "clear_of": "complex.feature.hot_tub_placeholder",
            "minimum_clearance_mm": to_mm(cfg.BEAM_FEATURE_CLEARANCE),
        },
    )

    # Shed-style roof attached high on the house wall and sloping down toward
    # the outside edge of the upper deck.
    roof_x = -cfg.ROOF_OVERHANG
    roof_front_y = -cfg.UPPER_DECK_DEPTH - cfg.ROOF_OVERHANG
    roof_back_y = cfg.ROOF_OVERHANG
    roof_w = cfg.UPPER_DECK_WIDTH + 2 * cfg.ROOF_OVERHANG
    roof_back_z = cfg.UPPER_DECK_ELEVATION + cfg.ROOF_HEIGHT_ABOVE_UPPER
    if cfg.ROOF_STYLE != "shed":
        raise ValueError(f"Unsupported ROOF_STYLE: {cfg.ROOF_STYLE!r}; expected 'shed'")
    roof_drop = cfg.ROOF_SLOPE_DROP
    roof_front_z = roof_back_z - roof_drop

    # Note: prism_between(width) extends the prism from the start-end axis
    # in one perpendicular direction (positive x for y-spanning prisms). So
    # start/end must be at roof_x (left edge), not roof_x + roof_w / 2.
    builder.add_prism(
        "roof",
        "UpperDeckShedRoofCover",
        (roof_x, roof_back_y, roof_back_z),
        (roof_x, roof_front_y, roof_front_z),
        roof_w,
        cfg.ROOF_THICKNESS,
        (0.18, 0.20, 0.22),
    )

    if cfg.ROOF_ATTACH_TO_HOUSE:
        builder.add_box(
            "roof-framing",
            "RoofHouseLedger",
            roof_w,
            cfg.ROOF_RAFTER_WIDTH,
            cfg.ROOF_RAFTER_HEIGHT,
            roof_x,
            -cfg.ROOF_RAFTER_WIDTH / 2,
            roof_back_z - cfg.ROOF_RAFTER_HEIGHT,
            (0.92, 0.92, 0.90),
            drawing_label=True,
        )

    rafter_x = roof_x + cfg.ROOF_RAFTER_SPACING
    rafter_index = 1
    while rafter_x < roof_x + roof_w - cfg.ROOF_RAFTER_WIDTH:
        builder.add_prism(
            "roof-framing",
            f"RoofRafter_{rafter_index:02d}",
            (rafter_x, roof_back_y, roof_back_z - cfg.ROOF_THICKNESS),
            (rafter_x, roof_front_y, roof_front_z - cfg.ROOF_THICKNESS),
            cfg.ROOF_RAFTER_WIDTH,
            cfg.ROOF_RAFTER_HEIGHT,
            (0.92, 0.92, 0.90),
        )
        rafter_x = rafter_x + cfg.ROOF_RAFTER_SPACING
        rafter_index += 1

    builder.add_box(
        "roof-framing",
        "RoofFrontBeam",
        roof_w,
        cfg.BEAM_WIDTH,
        cfg.BEAM_HEIGHT,
        roof_x,
        roof_front_y,
        roof_front_z - cfg.ROOF_THICKNESS - cfg.BEAM_HEIGHT,
        cfg.RAILING_COLOR,
    )
    builder.add_box(
        "roof",
        "RoofFrontFascia",
        roof_w,
        cfg.ROOF_RAFTER_WIDTH,
        cfg.ROOF_FASCIA_HEIGHT,
        roof_x,
        roof_front_y,
        roof_front_z - cfg.ROOF_FASCIA_HEIGHT,
        cfg.RAILING_COLOR,
    )
    builder.add_prism(
        "roof",
        "RoofLeftFascia",
        (roof_x, roof_back_y, roof_back_z),
        (roof_x, roof_front_y, roof_front_z),
        cfg.ROOF_RAFTER_WIDTH,
        cfg.ROOF_FASCIA_HEIGHT,
        cfg.RAILING_COLOR,
    )
    builder.add_prism(
        "roof",
        "RoofRightFascia",
        (roof_x + roof_w, roof_back_y, roof_back_z),
        (roof_x + roof_w, roof_front_y, roof_front_z),
        cfg.ROOF_RAFTER_WIDTH,
        cfg.ROOF_FASCIA_HEIGHT,
        cfg.RAILING_COLOR,
    )

    post = 8 * INCH
    front_post_height = roof_front_z - cfg.ROOF_THICKNESS - cfg.BEAM_HEIGHT - cfg.UPPER_DECK_ELEVATION
    front_post_count = max(2, int(cfg.ROOF_FRONT_POSTS))
    front_post_span = cfg.UPPER_DECK_WIDTH - post
    for index in range(front_post_count):
        ratio = index / (front_post_count - 1)
        post_x = front_post_span * ratio
        builder.add_box(
            "roof-framing",
            f"RoofFrontPost_{index + 1}",
            post,
            post,
            front_post_height,
            post_x,
            -cfg.UPPER_DECK_DEPTH,
            cfg.UPPER_DECK_ELEVATION,
            (0.92, 0.92, 0.90),
        )

    if not cfg.ROOF_ATTACH_TO_HOUSE:
        rear_post_height = roof_back_z - cfg.ROOF_THICKNESS - cfg.UPPER_DECK_ELEVATION
        for index, post_x in enumerate((ZERO, cfg.UPPER_DECK_WIDTH - post), 1):
            builder.add_box(
                "roof-framing",
                f"RoofRearPost_{index}",
                post,
                post,
                rear_post_height,
                post_x,
                -post,
                cfg.UPPER_DECK_ELEVATION,
                (0.92, 0.92, 0.90),
            )

    fan_x = cfg.UPPER_DECK_WIDTH / 2
    fan_y = -cfg.UPPER_DECK_DEPTH / 2
    fan_z = (roof_back_z + roof_front_z) / 2 - 28 * INCH
    builder.add_cylinder(
        "feature",
        "CoveredDeckFanDownrod",
        (fan_x, fan_y, (roof_back_z + roof_front_z) / 2 - cfg.ROOF_RAFTER_HEIGHT),
        (fan_x, fan_y, fan_z),
        1.25 * INCH,
        cfg.RAILING_COLOR,
    )
    builder.add_cylinder(
        "feature",
        "CoveredDeckFanMotor",
        (fan_x, fan_y, fan_z - 3 * INCH),
        (fan_x, fan_y, fan_z + 3 * INCH),
        7 * INCH,
        cfg.RAILING_COLOR,
    )
    blade = cfg.FAN_DIAMETER / 2

    def _fan_blade(name: str, direction_x: float, direction_y: float) -> None:
        hub_radius = 7 * INCH
        root_half_width = cfg.FAN_BLADE_WIDTH * 0.32
        tip_half_width = cfg.FAN_BLADE_WIDTH / 2
        px, py = -direction_y, direction_x
        root_x = to_mm(fan_x) + direction_x * to_mm(hub_radius)
        root_y = to_mm(fan_y) + direction_y * to_mm(hub_radius)
        tip_x = to_mm(fan_x) + direction_x * to_mm(blade)
        tip_y = to_mm(fan_y) + direction_y * to_mm(blade)
        profile = Plane.XY * Polyline(
            (root_x + px * to_mm(root_half_width), root_y + py * to_mm(root_half_width)),
            (tip_x + px * to_mm(tip_half_width), tip_y + py * to_mm(tip_half_width)),
            (tip_x - px * to_mm(tip_half_width), tip_y - py * to_mm(tip_half_width)),
            (root_x - px * to_mm(root_half_width), root_y - py * to_mm(root_half_width)),
            close=True,
        )
        shape = extrude(make_face(profile), amount=to_mm(INCH)).solid().translate((0.0, 0.0, to_mm(fan_z)))
        builder.add_shape(
            "feature",
            name,
            shape,
            cfg.SKIRTING_COLOR,
            Dimensions(to_mm(blade), to_mm(cfg.FAN_BLADE_WIDTH), to_mm(INCH)),
            placement=(fan_x, fan_y, fan_z),
            properties={"complex_type": "tapered_ceiling_fan_blade", "assembly_role": "fan_blade"},
        )

    _fan_blade("CoveredDeckFanBlade_X_Pos", 1.0, 0.0)
    _fan_blade("CoveredDeckFanBlade_X_Neg", -1.0, 0.0)
    _fan_blade("CoveredDeckFanBlade_Y_Pos", 0.0, 1.0)
    _fan_blade("CoveredDeckFanBlade_Y_Neg", 0.0, -1.0)

    # Fireplace body height matches roof at its front face (y=-DEPTH) so it
    # touches the roof without extending through it.  The chimney extends above.
    _roof_back_y = cfg.ROOF_OVERHANG
    _roof_front_y = -cfg.UPPER_DECK_DEPTH - cfg.ROOF_OVERHANG
    _roof_back_z = cfg.UPPER_DECK_ELEVATION + cfg.ROOF_HEIGHT_ABOVE_UPPER
    _roof_front_z = _roof_back_z - cfg.ROOF_SLOPE_DROP
    _fp_front_y = -cfg.FIREPLACE_DEPTH
    _ratio = (_fp_front_y - _roof_back_y) / (_roof_front_y - _roof_back_y)
    _fireplace_height_mm = to_mm(_roof_back_z) + _ratio * (to_mm(_roof_front_z) - to_mm(_roof_back_z))
    fireplace_body_height = mm(_fireplace_height_mm)
    # Opening on the right face (x=FIREPLACE_WIDTH), facing the deck. Cut it
    # into the masonry rather than representing it as a dark surface patch.
    fireplace_face_x = cfg.FIREPLACE_WIDTH
    fireplace_center_y = -cfg.FIREPLACE_DEPTH / 2
    firebox_y = fireplace_center_y - cfg.FIREPLACE_OPENING_WIDTH / 2
    firebox_z = cfg.UPPER_DECK_ELEVATION + 12 * INCH
    fireplace_body = box(
        cfg.FIREPLACE_WIDTH,
        cfg.FIREPLACE_DEPTH,
        fireplace_body_height,
        origin=(ZERO, -cfg.FIREPLACE_DEPTH, ZERO),
    )
    firebox_void = box(
        14 * INCH,
        cfg.FIREPLACE_OPENING_WIDTH,
        cfg.FIREPLACE_OPENING_HEIGHT,
        origin=(cfg.FIREPLACE_WIDTH - 14 * INCH, firebox_y, firebox_z),
    )
    builder.add_shape(
        "fireplace",
        "FireplaceMasonryBody",
        fireplace_body.cut(firebox_void),
        cfg.BRICK_COLOR,
        Dimensions(to_mm(cfg.FIREPLACE_WIDTH), to_mm(cfg.FIREPLACE_DEPTH), to_mm(fireplace_body_height)),
        drawing_label=True,
        properties={
            "complex_type": "masonry_fireplace_with_firebox",
            "assembly_role": "fireplace_enclosure",
            "opening_for": "complex.fireplace.fireplace_opening",
            "wall_opening": True,
        },
    )
    builder.add_box(
        "fireplace",
        "FireplaceOpening",
        12 * INCH,
        cfg.FIREPLACE_OPENING_WIDTH,
        cfg.FIREPLACE_OPENING_HEIGHT,
        fireplace_face_x - 12 * INCH,
        firebox_y,
        firebox_z,
        (0.03, 0.03, 0.03),
        properties={
            "complex_type": "electric_firebox",
            "assembly_role": "recessed_insert_cavity",
            "opening_in": "complex.fireplace.fireplace_masonry_body",
        },
    )
    builder.add_box(
        "fireplace",
        "ElectricFireplaceGlow",
        1.5 * INCH,
        5 * FOOT,
        cfg.FIREPLACE_OPENING_HEIGHT - 6 * INCH,
        fireplace_face_x + INCH,
        fireplace_center_y - (5 * FOOT) / 2,
        cfg.UPPER_DECK_ELEVATION + 15 * INCH,
        (0.90, 0.28, 0.08),
    )
    builder.add_box(
        "fireplace",
        "FireplaceTV",
        INCH,
        cfg.TV_WIDTH,
        cfg.TV_HEIGHT,
        fireplace_face_x + 1.5 * INCH,
        fireplace_center_y - cfg.TV_WIDTH / 2,
        cfg.UPPER_DECK_ELEVATION + 56 * INCH,
        (0.02, 0.02, 0.025),
    )
    # Fireplace mantel mounted on the right face above the opening
    mantel_depth = 4 * INCH  # how far it protrudes from the face (+x)
    mantel_height = 2 * INCH
    mantel_width = cfg.FIREPLACE_OPENING_WIDTH + 2 * FOOT  # wider than opening
    builder.add_box(
        "fireplace",
        "FireplaceMantel",
        mantel_depth,  # x-dimension: protrudes from face
        mantel_width,  # y-dimension: spans wider than opening
        mantel_height,  # z-dimension: thickness
        fireplace_face_x,  # x: starts at right face, extends outward
        fireplace_center_y - mantel_width / 2,  # centered on fireplace
        cfg.UPPER_DECK_ELEVATION + 12 * INCH + cfg.FIREPLACE_OPENING_HEIGHT + 2 * INCH,  # above opening
        (0.15, 0.10, 0.05),
    )
    # Chimney at the back of fireplace, centered on x (near y=0, house side)
    chimney_center_x = cfg.FIREPLACE_WIDTH / 2
    chimney_x = chimney_center_x - cfg.CHIMNEY_WIDTH / 2
    chimney_y = -cfg.CHIMNEY_DEPTH
    chimney_bottom_z = fireplace_body_height
    # Chimney top extends above the roof peak regardless of fireplace height
    roof_peak_z = cfg.UPPER_DECK_ELEVATION + cfg.ROOF_HEIGHT_ABOVE_UPPER
    chimney_top_z = roof_peak_z + cfg.CHIMNEY_HEIGHT_ABOVE_ROOF
    builder.add_box(
        "fireplace",
        "FireplaceChimney",
        cfg.CHIMNEY_WIDTH,
        cfg.CHIMNEY_DEPTH,
        chimney_top_z - chimney_bottom_z,
        chimney_x,
        chimney_y,
        chimney_bottom_z,
        cfg.BRICK_COLOR,
    )
    # Chimney cap
    builder.add_box(
        "fireplace",
        "FireplaceChimneyCap",
        cfg.CHIMNEY_WIDTH + 2 * cfg.CHIMNEY_CAP_OVERHANG,
        cfg.CHIMNEY_DEPTH + 2 * cfg.CHIMNEY_CAP_OVERHANG,
        2 * INCH,
        chimney_x - cfg.CHIMNEY_CAP_OVERHANG,
        chimney_y - cfg.CHIMNEY_CAP_OVERHANG,
        chimney_top_z,
        (0.10, 0.10, 0.10),
    )
    # Flue opening in chimney face
    builder.add_box(
        "fireplace",
        "FireplaceFlueHole",
        6 * INCH,
        INCH,
        6 * INCH,
        chimney_center_x - 3 * INCH,
        chimney_y - INCH,
        chimney_bottom_z + 2 * FOOT,
        (0.02, 0.02, 0.02),
    )
    door_frame = 2 * INCH
    builder.add_box(
        "feature",
        "SlidingDoor",
        cfg.DOOR_WIDTH - 2 * door_frame,
        1 * INCH,
        cfg.DOOR_HEIGHT - 2 * door_frame,
        sliding_door_x + door_frame,
        sliding_door_y,
        cfg.UPPER_DECK_ELEVATION + door_frame,
        (0.55, 0.70, 0.82),
        drawing_label=True,
        properties={
            "complex_type": "sliding_glass_door",
            "assembly_role": "glazing",
            "panel_count": 2,
        },
    )
    for frame_name, length, depth, height, x, y, z in (
        (
            "SlidingDoorFrameLeft",
            door_frame,
            3 * INCH,
            cfg.DOOR_HEIGHT,
            sliding_door_x,
            sliding_door_y,
            cfg.UPPER_DECK_ELEVATION,
        ),
        (
            "SlidingDoorFrameRight",
            door_frame,
            3 * INCH,
            cfg.DOOR_HEIGHT,
            sliding_door_x + cfg.DOOR_WIDTH - door_frame,
            sliding_door_y,
            cfg.UPPER_DECK_ELEVATION,
        ),
        (
            "SlidingDoorFrameHead",
            cfg.DOOR_WIDTH,
            3 * INCH,
            door_frame,
            sliding_door_x,
            sliding_door_y,
            cfg.UPPER_DECK_ELEVATION + cfg.DOOR_HEIGHT - door_frame,
        ),
        (
            "SlidingDoorFrameSill",
            cfg.DOOR_WIDTH,
            3 * INCH,
            door_frame,
            sliding_door_x,
            sliding_door_y,
            cfg.UPPER_DECK_ELEVATION,
        ),
        (
            "SlidingDoorMeetingRail",
            door_frame,
            3 * INCH,
            cfg.DOOR_HEIGHT - 2 * door_frame,
            sliding_door_x + cfg.DOOR_WIDTH / 2 - door_frame / 2,
            sliding_door_y,
            cfg.UPPER_DECK_ELEVATION + door_frame,
        ),
    ):
        builder.add_box(
            "feature",
            frame_name,
            length,
            depth,
            height,
            x,
            y,
            z,
            cfg.RAILING_COLOR,
            parent_id="complex.feature.sliding_door",
            properties={"complex_type": "door_frame_member", "assembly_role": "sliding_door_frame"},
        )

    kitchen_x = 10.5 * cfg.FOOT
    kitchen_y = -2.5 * cfg.FOOT
    builder.add_box(
        "outdoor-kitchen",
        "OutdoorKitchenCabinetRun",
        cfg.KITCHEN_LENGTH,
        cfg.KITCHEN_DEPTH,
        cfg.KITCHEN_COUNTER_HEIGHT - cfg.KITCHEN_COUNTER_THICKNESS,
        kitchen_x,
        kitchen_y,
        cfg.UPPER_DECK_ELEVATION,
        (0.12, 0.12, 0.12),
        drawing_label=True,
    )
    sink_x = kitchen_x + 18 * INCH
    sink_y = kitchen_y + (cfg.KITCHEN_DEPTH - cfg.KITCHEN_SINK_DEPTH) / 2
    counter_z = cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT - cfg.KITCHEN_COUNTER_THICKNESS
    countertop = box(
        cfg.KITCHEN_LENGTH + 4 * INCH,
        cfg.KITCHEN_DEPTH + 4 * INCH,
        cfg.KITCHEN_COUNTER_THICKNESS,
        origin=(kitchen_x - 2 * INCH, kitchen_y - 2 * INCH, counter_z),
    )
    sink_cutout = box(
        cfg.KITCHEN_SINK_WIDTH,
        cfg.KITCHEN_SINK_DEPTH,
        cfg.KITCHEN_COUNTER_THICKNESS,
        origin=(sink_x, sink_y, counter_z),
    )
    builder.add_shape(
        "outdoor-kitchen",
        "OutdoorKitchenCountertop",
        countertop.cut(sink_cutout),
        (0.45, 0.45, 0.42),
        Dimensions(
            to_mm(cfg.KITCHEN_LENGTH + 4 * INCH),
            to_mm(cfg.KITCHEN_DEPTH + 4 * INCH),
            to_mm(cfg.KITCHEN_COUNTER_THICKNESS),
        ),
        placement=(kitchen_x - 2 * INCH, kitchen_y - 2 * INCH, counter_z),
        properties={
            "complex_type": "countertop_with_sink_cutout",
            "assembly_role": "work_surface",
            "opening_for": "complex.outdoor_kitchen.outdoor_kitchen_sink_basin",
        },
    )
    sink_outer = box(
        cfg.KITCHEN_SINK_WIDTH,
        cfg.KITCHEN_SINK_DEPTH,
        5 * INCH,
        origin=(sink_x, sink_y, cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT - 5 * INCH),
    )
    sink_inner = box(
        cfg.KITCHEN_SINK_WIDTH - 2 * INCH,
        cfg.KITCHEN_SINK_DEPTH - 2 * INCH,
        4.5 * INCH,
        origin=(sink_x + INCH, sink_y + INCH, cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT - 4.5 * INCH),
    )
    builder.add_shape(
        "outdoor-kitchen",
        "OutdoorKitchenSinkBasin",
        sink_outer.cut(sink_inner),
        (0.12, 0.15, 0.16),
        Dimensions(to_mm(cfg.KITCHEN_SINK_WIDTH), to_mm(cfg.KITCHEN_SINK_DEPTH), to_mm(5 * INCH)),
        placement=(sink_x, sink_y, cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT - 5 * INCH),
        properties={"complex_type": "open_sink_basin", "assembly_role": "sink"},
    )
    builder.add_cylinder(
        "outdoor-kitchen",
        "OutdoorKitchenFaucet",
        (
            sink_x + cfg.KITCHEN_SINK_WIDTH / 2,
            sink_y + cfg.KITCHEN_SINK_DEPTH,
            cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT,
        ),
        (
            sink_x + cfg.KITCHEN_SINK_WIDTH / 2,
            sink_y + cfg.KITCHEN_SINK_DEPTH,
            cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT + 10 * INCH,
        ),
        INCH,
        (0.75, 0.75, 0.72),
    )
    builder.add_cylinder(
        "outdoor-kitchen",
        "OutdoorKitchenFaucetSpout",
        (
            sink_x + cfg.KITCHEN_SINK_WIDTH / 2,
            sink_y + cfg.KITCHEN_SINK_DEPTH,
            cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT + 10 * INCH,
        ),
        (
            sink_x + cfg.KITCHEN_SINK_WIDTH / 2,
            sink_y + cfg.KITCHEN_SINK_DEPTH - 7 * INCH,
            cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT + 10 * INCH,
        ),
        0.75 * INCH,
        (0.75, 0.75, 0.72),
        parent_id="complex.outdoor_kitchen.outdoor_kitchen_faucet",
        properties={"complex_type": "faucet_spout", "assembly_role": "water_outlet"},
    )
    # Standalone grill placed to the right of the shortened kitchen counter
    grill_x = kitchen_x + cfg.KITCHEN_LENGTH + 6 * INCH
    builder.add_box(
        "outdoor-kitchen",
        "OutdoorKitchenGrill",
        cfg.KITCHEN_GRILL_WIDTH,
        cfg.KITCHEN_DEPTH + 2 * INCH,
        36 * INCH,
        grill_x,
        kitchen_y - INCH,
        cfg.UPPER_DECK_ELEVATION,
        (0.05, 0.05, 0.05),
    )
    for index, door_x in enumerate((kitchen_x + 12 * INCH, kitchen_x + 36 * INCH, kitchen_x + 60 * INCH), 1):
        builder.add_box(
            "outdoor-kitchen",
            f"OutdoorKitchenDoor_{index}",
            cfg.KITCHEN_DOOR_WIDTH,
            INCH,
            24 * INCH,
            door_x,
            kitchen_y - INCH,
            cfg.UPPER_DECK_ELEVATION + 8 * INCH,
            (0.22, 0.22, 0.22),
        )

    hot_tub_z = cfg.LOWER_DECK_ELEVATION - (cfg.HOT_TUB_TOTAL_HEIGHT - cfg.HOT_TUB_ABOVE_DECK)
    hot_tub_outer = box(
        cfg.HOT_TUB_WIDTH,
        cfg.HOT_TUB_DEPTH,
        cfg.HOT_TUB_TOTAL_HEIGHT,
        origin=(hot_tub_x, hot_tub_y, hot_tub_z),
    )
    hot_tub_basin = box(
        cfg.HOT_TUB_WIDTH - 2 * cfg.HOT_TUB_RIM_WIDTH,
        cfg.HOT_TUB_DEPTH - 2 * cfg.HOT_TUB_RIM_WIDTH,
        cfg.HOT_TUB_TOTAL_HEIGHT - cfg.HOT_TUB_SHELL_THICKNESS,
        origin=(
            hot_tub_x + cfg.HOT_TUB_RIM_WIDTH,
            hot_tub_y + cfg.HOT_TUB_RIM_WIDTH,
            hot_tub_z + cfg.HOT_TUB_SHELL_THICKNESS,
        ),
    )
    builder.add_shape(
        "feature",
        "HotTubSpaShell",
        hot_tub_outer.cut(hot_tub_basin),
        (0.08, 0.10, 0.12),
        Dimensions(to_mm(cfg.HOT_TUB_WIDTH), to_mm(cfg.HOT_TUB_DEPTH), to_mm(cfg.HOT_TUB_TOTAL_HEIGHT)),
        placement=(hot_tub_x, hot_tub_y, hot_tub_z),
        drawing_label=True,
        stable_id="complex.feature.hot_tub_placeholder",
        properties={
            "label": "Lower Deck Hot Tub Spa",
            "complex_type": "recessed_hot_tub_spa",
            "assembly_role": "spa_shell",
            "replaces_placeholder": True,
            "service_access_side": "south",
        },
    )
    builder.add_box(
        "pool",
        "HotTubWater",
        cfg.HOT_TUB_WIDTH - 2 * cfg.HOT_TUB_RIM_WIDTH,
        cfg.HOT_TUB_DEPTH - 2 * cfg.HOT_TUB_RIM_WIDTH,
        1 * INCH,
        hot_tub_x + cfg.HOT_TUB_RIM_WIDTH,
        hot_tub_y + cfg.HOT_TUB_RIM_WIDTH,
        hot_tub_z + cfg.HOT_TUB_TOTAL_HEIGHT - cfg.HOT_TUB_WATER_OFFSET,
        cfg.WATER_COLOR,
        parent_id="complex.feature.hot_tub_placeholder",
        properties={"complex_type": "spa_water_surface", "assembly_role": "water"},
    )
    for step_index in range(2):
        builder.add_box(
            "feature",
            f"HotTubAccessStep_{step_index + 1}",
            cfg.HOT_TUB_STEP_WIDTH,
            cfg.HOT_TUB_STEP_DEPTH,
            cfg.HOT_TUB_STEP_HEIGHT * (step_index + 1),
            hot_tub_x + (cfg.HOT_TUB_WIDTH - cfg.HOT_TUB_STEP_WIDTH) / 2,
            hot_tub_y - cfg.HOT_TUB_STEP_DEPTH * (2 - step_index),
            cfg.LOWER_DECK_ELEVATION,
            cfg.SKIRTING_COLOR,
            parent_id="complex.feature.hot_tub_placeholder",
            properties={"complex_type": "spa_access_step", "assembly_role": "access_step"},
        )
    builder.add_box(
        "structure",
        "HotTubPlatform",
        cfg.HOT_TUB_WIDTH,
        cfg.HOT_TUB_DEPTH,
        cfg.LOWER_DECK_ELEVATION,
        hot_tub_x,
        hot_tub_y,
        ZERO,
        (0.15, 0.15, 0.15),
    )

    rail_height = cfg.RAILING_HEIGHT
    rail_thickness = cfg.RAILING_RAIL_SIZE
    post_thickness = cfg.RAILING_POST_SIZE

    def rail_segment(name: str, start: Point2, end: Point2, z: Length) -> None:
        builder.add_prism(
            "railing",
            name,
            (start[0], start[1], z + rail_height - rail_thickness),
            (end[0], end[1], z + rail_height - rail_thickness),
            rail_thickness,
            rail_thickness,
            cfg.RAILING_COLOR,
        )
        # Midrail at half height
        builder.add_cylinder(
            "railing",
            f"{name}Midrail",
            (start[0], start[1], z + rail_height / 2),
            (end[0], end[1], z + rail_height / 2),
            rail_thickness / 2,
            cfg.RAILING_COLOR,
        )
        dx = to_mm(end[0] - start[0])
        dy = to_mm(end[1] - start[1])
        run = math.hypot(dx, dy)
        baluster_count = max(1, math.ceil(run / to_mm(cfg.RAILING_BALUSTER_MAX_SPACING)) - 1)
        for index in range(1, baluster_count + 1):
            ratio = index / (baluster_count + 1)
            baluster_x = mm(to_mm(start[0]) + dx * ratio)
            baluster_y = mm(to_mm(start[1]) + dy * ratio)
            builder.add_cylinder(
                "railing",
                f"{name}Baluster_{index:03d}",
                (baluster_x, baluster_y, z + rail_thickness),
                (baluster_x, baluster_y, z + rail_height - rail_thickness),
                cfg.RAILING_BALUSTER_SIZE / 2,
                cfg.RAILING_COLOR,
                parent_id=f"complex.railing.{_slug(name)}",
                properties={
                    "complex_type": "railing_baluster",
                    "assembly_role": "guard_infill",
                    "maximum_spacing_mm": to_mm(cfg.RAILING_BALUSTER_MAX_SPACING),
                },
            )

    def rail_post(name: str, x: Length, y: Length, z: Length) -> None:
        builder.add_box(
            "railing",
            name,
            post_thickness,
            post_thickness,
            rail_height,
            x - post_thickness / 2,
            y - post_thickness / 2,
            z,
            cfg.RAILING_COLOR,
        )

    def line_frame(start: Point2, end: Point2) -> tuple[float, float, float, float, float]:
        dx = to_mm(end[0] - start[0])
        dy = to_mm(end[1] - start[1])
        run = math.hypot(dx, dy)
        return dx, dy, run, -dy / run, dx / run

    def stair_run(
        prefix: str,
        start: Point2,
        end: Point2,
        start_z: Length,
        end_z: Length,
        width: Length = cfg.STAIR_WIDTH,
        left_rail_x_shift: Length = ZERO,
    ) -> None:
        dx, dy, run, px, py = line_frame(start, end)
        steps = max(1, math.ceil(abs(to_mm(start_z - end_z)) / to_mm(cfg.MAX_RISER)))
        rise = to_mm(start_z - end_z) / steps
        direction_x = dx / run
        direction_y = dy / run
        riser_thickness = 1.25 * INCH
        riser_setback = (to_mm(cfg.TREAD_DEPTH) - to_mm(riser_thickness)) / 2
        for index in range(1, steps + 1):
            ratio = index / steps
            center_x = to_mm(start[0]) + dx * ratio
            center_y = to_mm(start[1]) + dy * ratio
            tread_z = to_mm(start_z) - rise * index
            builder.add_box(
                "stair",
                f"{prefix}Tread_{index:02d}",
                width,
                cfg.TREAD_DEPTH,
                cfg.DECK_BOARD_THICKNESS,
                mm(center_x - to_mm(width) / 2),
                mm(center_y - to_mm(cfg.TREAD_DEPTH) / 2),
                mm(tread_z - to_mm(cfg.DECK_BOARD_THICKNESS)),
                cfg.DECK_COLOR,
            )

            riser_center_x = center_x - direction_x * riser_setback
            riser_center_y = center_y - direction_y * riser_setback
            builder.add_box(
                "stair",
                f"{prefix}Riser_{index:02d}",
                width,
                riser_thickness,
                mm(abs(rise)),
                mm(riser_center_x - to_mm(width) / 2),
                mm(riser_center_y - to_mm(riser_thickness) / 2),
                mm(min(tread_z, tread_z + rise)),
                cfg.SKIRTING_COLOR,
            )

        stair_skirt_width = 2 * INCH
        stair_skirt_clearance = 0.125 * INCH
        rail_offset = to_mm(width) / 2
        skirt_offset = rail_offset + to_mm(stair_skirt_width) / 2 + to_mm(stair_skirt_clearance)
        for side_name, side_sign in (("Left", -1), ("Right", 1)):
            extra_shift = to_mm(left_rail_x_shift) if side_name == "Left" else 0.0
            offset = side_sign * rail_offset + extra_shift
            start_x = mm(to_mm(start[0]) + px * offset)
            start_y = mm(to_mm(start[1]) + py * offset)
            end_x = mm(to_mm(end[0]) + px * offset)
            end_y = mm(to_mm(end[1]) + py * offset)
            builder.add_cylinder(
                "railing",
                f"{prefix}{side_name}Handrail",
                (start_x, start_y, start_z + rail_height),
                (end_x, end_y, end_z + rail_height),
                rail_thickness,
                cfg.RAILING_COLOR,
            )
            builder.add_cylinder(
                "railing",
                f"{prefix}{side_name}Midrail",
                (start_x, start_y, start_z + rail_height / 2),
                (end_x, end_y, end_z + rail_height / 2),
                rail_thickness / 2,
                cfg.RAILING_COLOR,
            )
            skirt_extra = to_mm(left_rail_x_shift) if side_name == "Left" else 0.0
            skirt_start_x = mm(to_mm(start[0]) + px * (side_sign * skirt_offset + skirt_extra))
            skirt_start_y = mm(to_mm(start[1]) + py * (side_sign * skirt_offset + skirt_extra))
            skirt_end_x = mm(to_mm(end[0]) + px * (side_sign * skirt_offset + skirt_extra))
            skirt_end_y = mm(to_mm(end[1]) + py * (side_sign * skirt_offset + skirt_extra))
            builder.add_prism(
                "skirting",
                f"{prefix}{side_name}StairSkirt",
                (skirt_start_x, skirt_start_y, start_z - 8 * INCH),
                (skirt_end_x, skirt_end_y, end_z - 8 * INCH),
                stair_skirt_width,
                10 * INCH,
                cfg.SKIRTING_COLOR,
            )
            rail_post(f"{prefix}{side_name}Post_Top", start_x, start_y, start_z)
            rail_post(f"{prefix}{side_name}Post_Bottom", end_x, end_y, end_z)

    skirt_thickness = 2 * INCH
    upper_skirt_height = cfg.UPPER_DECK_ELEVATION - cfg.DECK_THICKNESS
    lower_skirt_height = cfg.LOWER_DECK_ELEVATION - cfg.DECK_THICKNESS
    upper_right_skirt_bottom = cfg.DECK_SKIRT_MIN_CLEARANCE_ABOVE_GRADE
    upper_right_skirt_profile = Plane.YZ * Polyline(
        (-to_mm(cfg.UPPER_DECK_DEPTH), to_mm(upper_right_skirt_bottom)),
        (-to_mm(cfg.LOWER_DECK_DEPTH), to_mm(cfg.LOWER_DECK_ELEVATION)),
        (0.0, to_mm(cfg.LOWER_DECK_ELEVATION)),
        (0.0, to_mm(upper_skirt_height)),
        (-to_mm(cfg.UPPER_DECK_DEPTH), to_mm(upper_skirt_height)),
        close=True,
    )
    upper_right_skirt = (
        extrude(
            make_face(upper_right_skirt_profile),
            amount=to_mm(skirt_thickness),
        )
        .solid()
        .translate((to_mm(cfg.UPPER_DECK_WIDTH), 0.0, 0.0))
    )
    builder.add_box(
        "skirting",
        "UpperDeckFrontSkirt",
        cfg.UPPER_DECK_WIDTH,
        skirt_thickness,
        upper_skirt_height,
        ZERO,
        -cfg.UPPER_DECK_DEPTH - skirt_thickness,
        ZERO,
        cfg.SKIRTING_COLOR,
    )
    upper_mid_beam_y = -cfg.UPPER_DECK_DEPTH / 2 - cfg.BEAM_WIDTH / 2
    upper_access_panel_max_y = upper_mid_beam_y - cfg.BEAM_FEATURE_CLEARANCE
    upper_access_panel_y = upper_access_panel_max_y - cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_WIDTH
    upper_access_panel_opening = box(
        skirt_thickness,
        cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_WIDTH,
        cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_HEIGHT,
        origin=(
            -skirt_thickness,
            upper_access_panel_y,
            cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_SILL,
        ),
    )
    upper_left_skirt = box(
        skirt_thickness,
        cfg.UPPER_DECK_DEPTH,
        upper_skirt_height,
        origin=(-skirt_thickness, -cfg.UPPER_DECK_DEPTH, ZERO),
    )
    builder.add_shape(
        "skirting",
        "UpperDeckLeftSkirt",
        upper_left_skirt.cut(upper_access_panel_opening),
        cfg.SKIRTING_COLOR,
        Dimensions(to_mm(skirt_thickness), to_mm(cfg.UPPER_DECK_DEPTH), to_mm(upper_skirt_height)),
        placement=(-skirt_thickness, -cfg.UPPER_DECK_DEPTH, ZERO),
        properties={
            "complex_type": "deck_skirt_with_access_opening",
            "assembly_role": "deck_enclosure",
            "opening_for": "complex.skirting.upper_deck_left_skirt_access_panel",
            "wall_opening": True,
        },
    )
    builder.add_shape(
        "skirting",
        "UpperDeckRightSkirt",
        upper_right_skirt,
        cfg.SKIRTING_COLOR,
        Dimensions(
            to_mm(skirt_thickness),
            to_mm(cfg.UPPER_DECK_DEPTH),
            to_mm(upper_skirt_height - upper_right_skirt_bottom),
        ),
        placement=(cfg.UPPER_DECK_WIDTH, -cfg.UPPER_DECK_DEPTH, upper_right_skirt_bottom),
        properties={
            "complex_type": "profiled_deck_skirt",
            "assembly_role": "deck_enclosure",
            "adjacent_to": ["complex.deck_board.lower_*", "complex.stair.lower_front_*"],
            "minimum_clearance_above_grade_mm": to_mm(cfg.DECK_SKIRT_MIN_CLEARANCE_ABOVE_GRADE),
        },
    )
    builder.add_box(
        "skirting",
        "LowerDeckRightSkirt",
        skirt_thickness,
        cfg.LOWER_DECK_DEPTH,
        lower_skirt_height,
        lower_x + cfg.LOWER_DECK_WIDTH,
        -cfg.LOWER_DECK_DEPTH,
        ZERO,
        cfg.SKIRTING_COLOR,
    )
    # Access panel on the yard side of UpperMidBeam, aligned with its skirt opening.
    access_panel_color = (0.30, 0.25, 0.20)
    builder.add_box(
        "skirting",
        "UpperDeckLeftSkirtAccessPanel",
        INCH,
        cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_WIDTH,
        cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_HEIGHT,
        -skirt_thickness - INCH,
        upper_access_panel_y,
        cfg.UPPER_LEFT_SKIRT_ACCESS_PANEL_SILL,
        access_panel_color,
        properties={
            "complex_type": "deck_skirt_access_panel",
            "assembly_role": "service_access",
            "opening_in": "complex.skirting.upper_deck_left_skirt",
            "clear_of": "complex.deck_framing.upper_mid_beam",
            "minimum_clearance_mm": to_mm(cfg.BEAM_FEATURE_CLEARANCE),
        },
    )
    # Access panel on LowerDeckRightSkirt — starts 6in from y=0, 6ft wide
    # Box spans y=-6ft-6in to y=-6in (top edge 6in from house wall)
    builder.add_box(
        "skirting",
        "LowerDeckRightSkirtAccessPanel",
        INCH,
        6 * FOOT,
        2 * FOOT,
        lower_x + cfg.LOWER_DECK_WIDTH + skirt_thickness,
        -6 * FOOT - 6 * INCH,
        ZERO + 6 * INCH,
        access_panel_color,
    )

    # ── Lighting elements on all skirts and stairs ─────────────────────────
    light_color = (0.95, 0.85, 0.10)  # warm yellow

    def _fixture_offsets(run_length: Length) -> list[float]:
        run_mm = to_mm(run_length)
        inset_mm = min(to_mm(cfg.DECK_LIGHT_END_INSET), run_mm / 2)
        usable_mm = max(0.0, run_mm - 2 * inset_mm)
        intervals = max(1, math.ceil(usable_mm / to_mm(cfg.DECK_LIGHT_MAX_SPACING)))
        return [inset_mm + usable_mm * index / intervals for index in range(intervals + 1)]

    def _add_skirt_lights(
        name: str,
        x: Length,
        y: Length,
        run_length: Length,
        z: Length,
        *,
        axis: str,
    ) -> None:
        for index, offset_mm in enumerate(_fixture_offsets(run_length), start=1):
            builder.add_box(
                "skirting",
                f"{name}Light_{index:02d}",
                cfg.DECK_LIGHT_PROJECTION if axis == "y" else cfg.DECK_LIGHT_FACE_WIDTH,
                cfg.DECK_LIGHT_FACE_WIDTH if axis == "y" else cfg.DECK_LIGHT_PROJECTION,
                cfg.DECK_LIGHT_FACE_HEIGHT,
                mm(to_mm(x) if axis == "y" else to_mm(x) + offset_mm - to_mm(cfg.DECK_LIGHT_FACE_WIDTH) / 2),
                mm(to_mm(y) + offset_mm - to_mm(cfg.DECK_LIGHT_FACE_WIDTH) / 2 if axis == "y" else to_mm(y)),
                z,
                light_color,
                properties={
                    "complex_type": "deck_skirt_light",
                    "assembly_role": "low_voltage_perimeter_lighting",
                    "illuminates": f"complex.skirting.{_slug(name)}",
                    "color_temperature_k": 2700,
                    "voltage_v": 12,
                    "aim": "downward",
                },
            )

    # UpperDeckFrontSkirt light (along x)
    _add_skirt_lights(
        "UpperDeckFrontSkirt",
        ZERO,
        -cfg.UPPER_DECK_DEPTH - skirt_thickness - cfg.DECK_LIGHT_PROJECTION,
        cfg.UPPER_DECK_WIDTH,
        cfg.DECK_LIGHT_HEIGHT_ABOVE_GRADE,
        axis="x",
    )
    # UpperDeckLeftSkirt light (along y)
    _add_skirt_lights(
        "UpperDeckLeftSkirt",
        -skirt_thickness - cfg.DECK_LIGHT_PROJECTION,
        -cfg.UPPER_DECK_DEPTH,
        cfg.UPPER_DECK_DEPTH,
        cfg.DECK_LIGHT_HEIGHT_ABOVE_GRADE,
        axis="y",
    )
    # UpperDeckRightSkirt light (along y)
    _add_skirt_lights(
        "UpperDeckRightSkirt",
        cfg.UPPER_DECK_WIDTH + skirt_thickness,
        -cfg.UPPER_DECK_DEPTH,
        cfg.UPPER_DECK_DEPTH,
        cfg.DECK_LIGHT_HEIGHT_ABOVE_GRADE,
        axis="y",
    )
    # LowerDeckRightSkirt light (along y)
    _add_skirt_lights(
        "LowerDeckRightSkirt",
        lower_x + cfg.LOWER_DECK_WIDTH + skirt_thickness,
        -cfg.LOWER_DECK_DEPTH,
        cfg.LOWER_DECK_DEPTH,
        cfg.DECK_LIGHT_HEIGHT_ABOVE_GRADE,
        axis="y",
    )
    # UpperDeckExtensionRightSkirt light (along y)
    _add_skirt_lights(
        "UpperDeckExtensionRightSkirt",
        cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH + skirt_thickness,
        -6 * cfg.FOOT,
        6 * cfg.FOOT,
        cfg.DECK_LIGHT_HEIGHT_ABOVE_GRADE,
        axis="y",
    )

    # Stair lighting — small light strips on stair tread risers
    def _add_stair_lights(
        prefix: str, start: Point2, end: Point2, start_z: Length, end_z: Length, width: Length = cfg.STAIR_WIDTH
    ) -> None:
        dx, dy, run, _px, _py = line_frame(start, end)
        steps = max(1, math.ceil(abs(to_mm(start_z - end_z)) / to_mm(cfg.MAX_RISER)))
        rise = to_mm(start_z - end_z) / steps
        for index in range(1, steps + 1):
            ratio = index / steps
            center_x = to_mm(start[0]) + dx * ratio
            center_y = to_mm(start[1]) + dy * ratio
            tread_z = to_mm(start_z) - rise * index
            lateral_ratios = (0.25, 0.75) if width > cfg.WIDE_STAIR_LIGHT_THRESHOLD else (0.5,)
            for fixture_index, lateral_ratio in enumerate(lateral_ratios, start=1):
                builder.add_box(
                    "stair",
                    f"{prefix}RiserLight_{index:02d}_{fixture_index:02d}",
                    cfg.DECK_LIGHT_FACE_WIDTH,
                    cfg.DECK_LIGHT_PROJECTION,
                    cfg.DECK_LIGHT_FACE_HEIGHT,
                    mm(
                        center_x
                        - to_mm(width) / 2
                        + to_mm(width) * lateral_ratio
                        - to_mm(cfg.DECK_LIGHT_FACE_WIDTH) / 2
                    ),
                    mm(center_y - to_mm(cfg.DECK_LIGHT_PROJECTION) / 2),
                    mm(tread_z + to_mm(INCH)),
                    light_color,
                    properties={
                        "complex_type": "stair_riser_light",
                        "assembly_role": "low_voltage_step_lighting",
                        "illuminates": f"complex.stair.{prefix.lower()}_riser_{index:02d}",
                        "color_temperature_k": 2700,
                        "voltage_v": 12,
                        "aim": "downward",
                    },
                )

    upper_stair_start = (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH / 2, -6 * cfg.FOOT)
    upper_stair_end = (upper_stair_start[0], -6 * cfg.FOOT - 44 * INCH)
    _add_stair_lights(
        "UpperStraight", upper_stair_start, upper_stair_end, cfg.UPPER_DECK_ELEVATION, cfg.LOWER_DECK_ELEVATION
    )
    stair_run("UpperStraight", upper_stair_start, upper_stair_end, cfg.UPPER_DECK_ELEVATION, cfg.LOWER_DECK_ELEVATION)
    add_deck_boards(
        "UpperExtension",
        cfg.UPPER_DECK_WIDTH,
        -6 * cfg.FOOT,
        cfg.STAIR_WIDTH,
        6 * cfg.FOOT,
        cfg.UPPER_DECK_ELEVATION,
        "y",
    )
    add_deck_framing(
        "UpperExtension",
        cfg.UPPER_DECK_WIDTH,
        -6 * cfg.FOOT,
        cfg.STAIR_WIDTH,
        6 * cfg.FOOT,
        cfg.UPPER_DECK_ELEVATION,
        [
            (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH, -6 * cfg.FOOT),
            (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH, -3 * cfg.FOOT),
        ],
    )
    builder.add_box(
        "skirting",
        "UpperDeckExtensionRightSkirt",
        skirt_thickness,
        6 * cfg.FOOT,
        upper_skirt_height - cfg.LOWER_DECK_ELEVATION,
        cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH,
        -6 * cfg.FOOT,
        cfg.LOWER_DECK_ELEVATION,
        cfg.SKIRTING_COLOR,
        properties={
            "complex_type": "deck_skirt_panel",
            "assembly_role": "deck_enclosure",
            "adjacent_to": ["complex.stair.upper_straight_*"],
            "lowest_adjacent_elevation_mm": to_mm(cfg.LOWER_DECK_ELEVATION),
        },
    )
    rail_segment(
        "ExtBackRail",
        (cfg.UPPER_DECK_WIDTH, ZERO),
        (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH, ZERO),
        cfg.UPPER_DECK_ELEVATION,
    )
    rail_segment(
        "ExtRightRail",
        (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH, ZERO),
        (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH, upper_stair_start[1]),
        cfg.UPPER_DECK_ELEVATION,
    )
    # Post at the ExtRightRail / ExtBackRail junction corner
    rail_post("ExtRightPost", cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH, ZERO, cfg.UPPER_DECK_ELEVATION)

    # Change 3: Lower deck stairs span full X-axis width of the lower deck.
    # Left handrail/posts shifted to x=25ft to clear UpperDeckRightSkirt.
    lower_stair_width = cfg.LOWER_DECK_WIDTH
    lower_stair_start = (lower_x + lower_stair_width / 2, -cfg.LOWER_DECK_DEPTH)
    lower_stair_end = (lower_stair_start[0], -cfg.UPPER_DECK_DEPTH)
    stair_run(
        "LowerFront",
        lower_stair_start,
        lower_stair_end,
        cfg.LOWER_DECK_ELEVATION,
        ZERO,
        lower_stair_width,
        left_rail_x_shift=6 * INCH,
    )
    _add_stair_lights(
        "LowerFront", lower_stair_start, lower_stair_end, cfg.LOWER_DECK_ELEVATION, ZERO, lower_stair_width
    )
    # No LowerDeckFrontSkirt needed when stairs span the full deck width

    stair_end_y = -cfg.UPPER_DECK_DEPTH
    pool_y = stair_end_y - cfg.DECK_TO_POOL_CLEARANCE - cfg.POOL_WIDTH - cfg.PATIO_BORDER
    pool_length = cfg.POOL_LENGTH
    pool_width = cfg.POOL_WIDTH
    # Retain the established left tile edge; the derived pool length makes the
    # outer edge of the right tile border end at the requested X coordinate.
    pool_x = cfg.POOL_TILE_SURROUND_MIN_X + cfg.PATIO_BORDER
    # 2' tile ground border around the pool.  Modeled as a ring of individual
    # 2' x 2' tile solids (not a single solid slab) so the pool surround reads
    # as laid tile rather than a monolithic pour.  The left/right strips span
    # the full width including corners; the near/far strips fill the gap
    # between them so no tile overlaps the pool footprint or another tile.
    tile_border = cfg.PATIO_BORDER
    tile_size = cfg.POOL_TILE_SIZE
    tile_thickness = 4 * INCH
    tile_z = -tile_thickness
    pool_surround_right_x = pool_x + pool_length + tile_border

    def _tile_run(name_prefix: str, x: Length, y: Length, run_length: Length, *, axis: str) -> None:
        """Lay a single-row strip of 2' x 2' tiles along the given axis."""
        step = tile_size
        index = 1
        if axis == "x":
            pos = x
            while pos < x + run_length - 1e-6 * MM:
                length = min(tile_size, x + run_length - pos)
                builder.add_box(
                    "site",
                    f"{name_prefix}_{index:02d}",
                    length,
                    tile_border,
                    tile_thickness,
                    pos,
                    y,
                    tile_z,
                    cfg.TILE_COLOR,
                )
                pos = pos + step
                index += 1
        else:  # axis == "y"
            pos = y
            while pos < y + run_length - 1e-6 * MM:
                length = min(tile_size, y + run_length - pos)
                builder.add_box(
                    "site",
                    f"{name_prefix}_{index:02d}",
                    tile_border,
                    length,
                    tile_thickness,
                    x,
                    pos,
                    tile_z,
                    cfg.TILE_COLOR,
                )
                pos = pos + step
                index += 1

    # Left/right strips include the corner tiles, so they span the full
    # pool width plus a border on each side.
    side_run = pool_width + 2 * tile_border
    _tile_run("PoolTileBorderLeft", pool_x - tile_border, pool_y - tile_border, side_run, axis="y")
    _tile_run("PoolTileBorderRight", pool_x + pool_length, pool_y - tile_border, side_run, axis="y")
    # Near/far strips fill the gap between the left/right strips (pool length
    # only, no corners) so tiles do not overlap.
    _tile_run("PoolTileBorderNear", pool_x, pool_y + pool_width, pool_length, axis="x")
    _tile_run("PoolTileBorderFar", pool_x, pool_y - tile_border, pool_length, axis="x")

    # Assemble every turf region into one semantic CAD element. The compound
    # preserves the hardscape and access cutouts while exporting/selecting as
    # a single yard-grass object.
    grass_regions: list[Any] = []

    # Grass strip between the lower deck stairs and the pool's near tile
    # border, spanning from tree line (x=0) to the pool surround right edge.
    lower_stair_end_y = -cfg.UPPER_DECK_DEPTH
    grass_strip_far_y = pool_y + pool_width + tile_border
    grass_strip_near_y = lower_stair_end_y
    grass_strip_x = ZERO
    grass_strip_length = pool_surround_right_x - grass_strip_x
    grass_strip_depth = grass_strip_near_y - grass_strip_far_y
    if to_mm(grass_strip_depth) > 0:
        grass_regions.append(
            box(
                grass_strip_length,
                grass_strip_depth,
                cfg.GRASS_THICKNESS,
                origin=(grass_strip_x, grass_strip_far_y, -cfg.GRASS_THICKNESS),
            )
        )

    # Grass south of the pool extends to the shed's far Y edge and across to
    # X=16.667yd.  A 10ft-wide connector at the shed-near end of the pool is
    # kept free of turf so a single vehicle can cross the evergreen screen.
    pool_south_far_y = pool_y - tile_border
    pool_south_start_y = cfg.SHED_Y
    pool_south_depth = pool_south_far_y - pool_south_start_y
    vehicle_connector_end_y = pool_south_far_y
    vehicle_connector_start_y = vehicle_connector_end_y - cfg.VEHICLE_CONNECTOR_CLEAR_WIDTH
    vehicle_connector_end_x = pool_x - tile_border
    if to_mm(pool_south_depth) > 0:
        grass_regions.append(
            box(
                cfg.POOL_SOUTH_GRASS_MAX_X - vehicle_connector_end_x,
                pool_south_depth,
                cfg.GRASS_THICKNESS,
                origin=(vehicle_connector_end_x, pool_south_start_y, -cfg.GRASS_THICKNESS),
            )
        )
        for start_y, depth in (
            (
                pool_south_start_y,
                vehicle_connector_start_y - pool_south_start_y,
            ),
            (
                vehicle_connector_end_y,
                pool_south_far_y - vehicle_connector_end_y,
            ),
        ):
            if to_mm(depth) > 0:
                grass_regions.append(
                    box(
                        vehicle_connector_end_x,
                        depth,
                        cfg.GRASS_THICKNESS,
                        origin=(ZERO, start_y, -cfg.GRASS_THICKNESS),
                    )
                )

    # RightGrassExtension occupies only the near/house side of the shared
    # boundary.  It stops exactly where PoolSouthGrass begins at y=-42ft.
    right_grass_x = pool_surround_right_x
    right_grass_length = cfg.POOL_SOUTH_GRASS_MAX_X - right_grass_x
    right_grass_far_y = pool_south_far_y
    right_grass_near_y = ZERO
    right_grass_depth = right_grass_near_y - right_grass_far_y
    if to_mm(right_grass_depth) > 0:
        grass_regions.append(
            box(
                right_grass_length,
                right_grass_depth,
                cfg.GRASS_THICKNESS,
                origin=(right_grass_x, right_grass_far_y, -cfg.GRASS_THICKNESS),
            )
        )

    # Paver field from the shed front at y=-24yd back to the house datum at
    # y=0, spanning from x=-17.117ft to the x=0 axis.
    shed_paver_width = cfg.SHED_PAVER_MAX_X - cfg.SHED_PAVER_MIN_X
    shed_paver_depth = cfg.SHED_PAVER_END_Y - cfg.SHED_PAVER_START_Y
    shed_access_pavers = box(
        shed_paver_width,
        shed_paver_depth,
        cfg.SHED_PAVER_THICKNESS,
        origin=(cfg.SHED_PAVER_MIN_X, cfg.SHED_PAVER_START_Y, -cfg.SHED_PAVER_THICKNESS),
    )
    vehicle_access_connector = box(
        vehicle_connector_end_x,
        cfg.VEHICLE_CONNECTOR_CLEAR_WIDTH,
        cfg.SHED_PAVER_THICKNESS,
        origin=(ZERO, vehicle_connector_start_y, -cfg.SHED_PAVER_THICKNESS),
    )
    unified_access_pavers = shed_access_pavers.fuse(vehicle_access_connector)
    builder.add_shape(
        "site",
        "UnifiedShedVehicleAccessPavers",
        unified_access_pavers,
        cfg.PAVER_COLOR,
        Dimensions(
            to_mm(vehicle_connector_end_x - cfg.SHED_PAVER_MIN_X),
            to_mm(shed_paver_depth),
            to_mm(cfg.SHED_PAVER_THICKNESS),
            extras={"vehicle_connector_clear_width_mm": to_mm(cfg.VEHICLE_CONNECTOR_CLEAR_WIDTH)},
        ),
        drawing_label=True,
        properties={
            "label": "Unified Shed and Vehicle Access Pavers",
            "complex_type": "connected_paver_access_assembly",
            "connection": "shed_access_pavers_to_pool_side_yard",
            "from_element_id": "complex.shed.yard_storage_shed",
            "to_element_id": "complex.site.pool_tile_border_far_01",
            "clear_width_mm": to_mm(cfg.VEHICLE_CONNECTOR_CLEAR_WIDTH),
            "location_intent": "shed-near_south_end_of_pool",
            "surface": "exterior_access_pavers",
        },
    )

    # Black ornamental fence on the right of the paver drive when looking
    # from the house toward the shed.  It sits just outside the paver edge so
    # it does not reduce the existing drive width.
    fence_parent_id = "complex.site.shed_access_fence"
    fence_x = cfg.SHED_PAVER_MIN_X - cfg.SHED_ACCESS_FENCE_POST_SIZE
    fence_depth = cfg.SHED_PAVER_END_Y - cfg.SHED_PAVER_START_Y
    fence_properties = {
        "complex_type": "ornamental_access_fence",
        "side": "right_when_viewed_house_to_shed",
        "finish": "black_powder_coat",
        "adjacent_to": "complex.site.unified_shed_vehicle_access_pavers",
    }
    builder.add_box(
        "site",
        "ShedAccessFence",
        cfg.SHED_ACCESS_FENCE_RAIL_SIZE,
        fence_depth,
        cfg.SHED_ACCESS_FENCE_RAIL_SIZE,
        fence_x,
        cfg.SHED_PAVER_START_Y,
        12 * INCH,
        cfg.FENCE_COLOR,
        drawing_label=True,
        properties={**fence_properties, "assembly_role": "lower_rail"},
    )
    builder.add_box(
        "site",
        "ShedAccessFenceTopRail",
        cfg.SHED_ACCESS_FENCE_RAIL_SIZE,
        fence_depth,
        cfg.SHED_ACCESS_FENCE_RAIL_SIZE,
        fence_x,
        cfg.SHED_PAVER_START_Y,
        cfg.SHED_ACCESS_FENCE_HEIGHT - 6 * INCH,
        cfg.FENCE_COLOR,
        parent_id=fence_parent_id,
        properties={**fence_properties, "assembly_role": "top_rail"},
    )
    fence_post_count = math.ceil(to_mm(fence_depth) / to_mm(cfg.SHED_ACCESS_FENCE_POST_SPACING)) + 1
    for post_index in range(fence_post_count):
        post_y = min(
            cfg.SHED_PAVER_START_Y + post_index * cfg.SHED_ACCESS_FENCE_POST_SPACING,
            cfg.SHED_PAVER_END_Y - cfg.SHED_ACCESS_FENCE_POST_SIZE,
        )
        builder.add_box(
            "site",
            f"ShedAccessFencePost_{post_index + 1:02d}",
            cfg.SHED_ACCESS_FENCE_POST_SIZE,
            cfg.SHED_ACCESS_FENCE_POST_SIZE,
            cfg.SHED_ACCESS_FENCE_HEIGHT,
            fence_x,
            post_y,
            ZERO,
            cfg.FENCE_COLOR,
            parent_id=fence_parent_id,
            properties={**fence_properties, "assembly_role": "post"},
        )
    fence_picket_count = math.floor(to_mm(fence_depth) / to_mm(cfg.SHED_ACCESS_FENCE_PICKET_SPACING)) + 1
    for picket_index in range(fence_picket_count):
        picket_y = cfg.SHED_PAVER_START_Y + picket_index * cfg.SHED_ACCESS_FENCE_PICKET_SPACING
        builder.add_box(
            "site",
            f"ShedAccessFencePicket_{picket_index + 1:03d}",
            cfg.SHED_ACCESS_FENCE_RAIL_SIZE,
            cfg.SHED_ACCESS_FENCE_RAIL_SIZE,
            cfg.SHED_ACCESS_FENCE_HEIGHT - 3 * INCH,
            fence_x,
            picket_y,
            ZERO,
            cfg.FENCE_COLOR,
            parent_id=fence_parent_id,
            properties={**fence_properties, "assembly_role": "picket"},
        )

    # Missing grass under the trees between PoolSouthGrass and PoolGrassStrip.
    # The pool and its tile border occupy
    # x=pool_x-tile_border..pool_surround_right_x
    # in the y range from pool_y-tile_border to pool_y+pool_width+tile_border.
    # The trees at x=0 need grass in that y gap.
    pool_mid_far_y = pool_y - tile_border  # -42ft, top of PoolSouthGrass
    pool_mid_near_y = pool_y + pool_width + tile_border  # -26ft, bottom of PoolGrassStrip
    pool_mid_depth = pool_mid_near_y - pool_mid_far_y
    if to_mm(pool_mid_depth) > 0:
        grass_regions.append(
            box(
                pool_x - tile_border,
                pool_mid_depth,
                cfg.GRASS_THICKNESS,
                origin=(ZERO, pool_mid_far_y, -cfg.GRASS_THICKNESS),
            )
        )

    if grass_regions:
        unified_grass = grass_regions[0].fuse(*grass_regions[1:])
        builder.add_shape(
            "site",
            "UnifiedYardGrass",
            unified_grass,
            cfg.GRASS_COLOR,
            Dimensions(
                to_mm(cfg.POOL_SOUTH_GRASS_MAX_X),
                to_mm(-cfg.SHED_Y),
                to_mm(cfg.GRASS_THICKNESS),
                extras={"region_count": len(grass_regions)},
            ),
            drawing_label=True,
            properties={
                "label": "Unified Yard Grass",
                "complex_type": "turf_assembly",
                "assembly_role": "yard_grass_with_hardscape_exclusions",
            },
        )

    # Sloped pool with the deep end on the "reverse" side (left, near the
    # house).  sloped_pool always places the deep end at +x, so the geometry
    # is mirrored about the pool's center x to put the deep end on the left.
    pool = sloped_pool(
        pool_length, pool_width, cfg.POOL_SHALLOW_DEPTH, cfg.POOL_DEEP_DEPTH, origin=(pool_x, pool_y, ZERO)
    )
    if cfg.POOL_DEEP_END_SIDE == "left":
        center_x_mm = to_mm(pool_x) + to_mm(pool_length) / 2
        pool = pool.mirror(Plane.YZ.offset(center_x_mm))
    elif cfg.POOL_DEEP_END_SIDE != "right":
        raise ValueError(f"Unsupported POOL_DEEP_END_SIDE: {cfg.POOL_DEEP_END_SIDE!r}; expected 'left' or 'right'")
    pool_shell = sloped_pool(
        pool_length + 2 * cfg.POOL_SHELL_THICKNESS,
        pool_width + 2 * cfg.POOL_SHELL_THICKNESS,
        cfg.POOL_SHALLOW_DEPTH + cfg.POOL_SHELL_THICKNESS,
        cfg.POOL_DEEP_DEPTH + cfg.POOL_SHELL_THICKNESS,
        origin=(pool_x - cfg.POOL_SHELL_THICKNESS, pool_y - cfg.POOL_SHELL_THICKNESS, ZERO),
    )
    if cfg.POOL_DEEP_END_SIDE == "left":
        pool_shell = pool_shell.mirror(Plane.YZ.offset(center_x_mm))
    builder.add_shape(
        "pool",
        "MainPoolShell",
        pool_shell.cut(pool),
        cfg.TILE_COLOR,
        Dimensions(
            to_mm(pool_length + 2 * cfg.POOL_SHELL_THICKNESS),
            to_mm(pool_width + 2 * cfg.POOL_SHELL_THICKNESS),
            to_mm(cfg.POOL_DEEP_DEPTH + cfg.POOL_SHELL_THICKNESS),
        ),
        placement=(pool_x - cfg.POOL_SHELL_THICKNESS, pool_y - cfg.POOL_SHELL_THICKNESS, ZERO),
        properties={
            "label": "Main Pool Structural Shell",
            "complex_type": "sloped_pool_shell",
            "assembly_role": "watertight_pool_enclosure",
            "contains": "complex.pool.main_pool_water_sloped5ft_to8ft",
            "shell_thickness_mm": to_mm(cfg.POOL_SHELL_THICKNESS),
        },
    )
    coping_outer = box(
        pool_length + 2 * cfg.POOL_COPING_WIDTH,
        pool_width + 2 * cfg.POOL_COPING_WIDTH,
        cfg.POOL_COPING_THICKNESS,
        origin=(pool_x - cfg.POOL_COPING_WIDTH, pool_y - cfg.POOL_COPING_WIDTH, ZERO),
    )
    coping_opening = box(
        pool_length,
        pool_width,
        cfg.POOL_COPING_THICKNESS,
        origin=(pool_x, pool_y, ZERO),
    )
    builder.add_shape(
        "site",
        "MainPoolCoping",
        coping_outer.cut(coping_opening),
        cfg.TILE_COLOR,
        Dimensions(
            to_mm(pool_length + 2 * cfg.POOL_COPING_WIDTH),
            to_mm(pool_width + 2 * cfg.POOL_COPING_WIDTH),
            to_mm(cfg.POOL_COPING_THICKNESS),
        ),
        placement=(pool_x - cfg.POOL_COPING_WIDTH, pool_y - cfg.POOL_COPING_WIDTH, ZERO),
        properties={
            "complex_type": "pool_coping_ring",
            "assembly_role": "pool_edge_finish",
            "surrounds": "complex.pool.main_pool_water_sloped5ft_to8ft",
        },
    )
    shallow_x = pool_x + pool_length - cfg.POOL_STEP_TREAD
    for step_index in range(3):
        builder.add_box(
            "pool",
            f"MainPoolEntryStep_{step_index + 1}",
            cfg.POOL_STEP_TREAD * (step_index + 1),
            cfg.POOL_STEP_WIDTH,
            cfg.POOL_STEP_RISE,
            shallow_x - cfg.POOL_STEP_TREAD * step_index,
            pool_y + (pool_width - cfg.POOL_STEP_WIDTH) / 2,
            -cfg.POOL_SHALLOW_DEPTH + cfg.POOL_STEP_RISE * step_index,
            cfg.TILE_COLOR,
            parent_id="complex.pool.main_pool_shell",
            properties={"complex_type": "pool_entry_step", "assembly_role": "entry_step"},
        )
    builder.add_shape(
        "pool",
        "MainPoolWater_Sloped5ftTo8ft",
        pool,
        cfg.WATER_COLOR,
        Dimensions(
            to_mm(pool_length),
            to_mm(pool_width),
            to_mm(cfg.POOL_DEEP_DEPTH),
            extras={"shallow_depth_mm": to_mm(cfg.POOL_SHALLOW_DEPTH)},
        ),
        placement=(pool_x, pool_y, ZERO),
        drawing_label=True,
        properties={
            "label": "Main Pool Water — Sloped 5 ft to 8 ft",
            "quantity_provenance": "exact_sloped_geometry",
            "deep_end_side": cfg.POOL_DEEP_END_SIDE,
        },
    )

    # Gable-roof yard shed wholly on the negative-X side.  Its near/front edge
    # starts at y=-24yd and the body extends another 20ft toward negative Y.
    shed_parent_id = "complex.shed.yard_storage_shed"
    shed_x = cfg.SHED_X
    shed_y = cfg.SHED_Y
    shed_front_y = shed_y + cfg.SHED_DEPTH
    shed_wall_top = cfg.SHED_WALL_HEIGHT
    shed_ridge_x = shed_x + cfg.SHED_WIDTH / 2
    shed_ridge_z = shed_wall_top + cfg.SHED_ROOF_RISE
    shed_common_properties = {
        "complex_type": "yard_storage_shed",
        "view_relationship": "negative-X yard; front at y=-24yd; body extends toward negative Y",
        "reference": "Photo 1 deck-to-yard view",
    }
    builder.add_box(
        "shed",
        "YardStorageShed",
        cfg.SHED_WIDTH,
        cfg.SHED_DEPTH,
        cfg.SHED_SLAB_THICKNESS,
        shed_x,
        shed_y,
        -cfg.SHED_SLAB_THICKNESS,
        (0.15, 0.15, 0.15),
        drawing_label=True,
        properties={**shed_common_properties, "assembly_role": "foundation"},
    )
    wall_thickness = 4 * INCH
    for name, length, depth, x, y in (
        ("ShedLeftWall", wall_thickness, cfg.SHED_DEPTH, shed_x, shed_y),
        (
            "ShedRightWall",
            wall_thickness,
            cfg.SHED_DEPTH,
            shed_x + cfg.SHED_WIDTH - wall_thickness,
            shed_y,
        ),
        ("ShedRearWall", cfg.SHED_WIDTH, wall_thickness, shed_x, shed_y),
        (
            "ShedFrontWall",
            cfg.SHED_WIDTH,
            wall_thickness,
            shed_x,
            shed_front_y - wall_thickness,
        ),
    ):
        wall_shape = box(length, depth, cfg.SHED_WALL_HEIGHT, origin=(x, y, ZERO))
        opening_for: str | None = None
        if name == "ShedRightWall":
            side_door_y = shed_front_y - cfg.SHED_SIDE_DOOR_WIDTH - 18 * INCH
            wall_shape = wall_shape.cut(
                box(
                    wall_thickness,
                    cfg.SHED_SIDE_DOOR_WIDTH,
                    cfg.SHED_SIDE_DOOR_HEIGHT,
                    origin=(x, side_door_y, ZERO),
                )
            )
            opening_for = "complex.shed.shed_side_service_door"
        elif name == "ShedFrontWall":
            front_door_x = shed_x + (cfg.SHED_WIDTH - cfg.SHED_FRONT_DOOR_WIDTH) / 2
            wall_shape = wall_shape.cut(
                box(
                    cfg.SHED_FRONT_DOOR_WIDTH,
                    wall_thickness,
                    cfg.SHED_FRONT_DOOR_HEIGHT,
                    origin=(front_door_x, y, ZERO),
                )
            )
            opening_for = "complex.shed.shed_front_double_door"
        wall_properties: dict[str, Any] = {**shed_common_properties, "assembly_role": "wall"}
        if opening_for is not None:
            wall_properties.update({"opening_for": opening_for, "wall_opening": True})
        builder.add_shape(
            "shed",
            name,
            wall_shape,
            cfg.SHED_SIDING_COLOR,
            Dimensions(to_mm(length), to_mm(depth), to_mm(cfg.SHED_WALL_HEIGHT)),
            placement=(x, y, ZERO),
            parent_id=shed_parent_id,
            properties=wall_properties,
        )

    roof_y = shed_y - cfg.SHED_ROOF_OVERHANG
    roof_depth = cfg.SHED_DEPTH + 2 * cfg.SHED_ROOF_OVERHANG
    builder.add_prism(
        "shed",
        "ShedRoofLeftSlope",
        (shed_x - cfg.SHED_ROOF_OVERHANG, roof_y, shed_wall_top),
        (shed_ridge_x, roof_y, shed_ridge_z),
        roof_depth,
        cfg.SHED_ROOF_THICKNESS,
        cfg.SHED_ROOF_COLOR,
        parent_id=shed_parent_id,
        properties={**shed_common_properties, "assembly_role": "roof"},
    )
    builder.add_prism(
        "shed",
        "ShedRoofRightSlope",
        (shed_ridge_x, roof_y, shed_ridge_z),
        (shed_x + cfg.SHED_WIDTH + cfg.SHED_ROOF_OVERHANG, roof_y, shed_wall_top),
        roof_depth,
        cfg.SHED_ROOF_THICKNESS,
        cfg.SHED_ROOF_COLOR,
        parent_id=shed_parent_id,
        properties={**shed_common_properties, "assembly_role": "roof"},
    )

    front_door_x = shed_x + (cfg.SHED_WIDTH - cfg.SHED_FRONT_DOOR_WIDTH) / 2
    builder.add_box(
        "shed",
        "ShedFrontDoubleDoor",
        cfg.SHED_FRONT_DOOR_WIDTH,
        1 * INCH,
        cfg.SHED_FRONT_DOOR_HEIGHT,
        front_door_x,
        shed_front_y,
        ZERO,
        cfg.SHED_TRIM_COLOR,
        parent_id=shed_parent_id,
        properties={**shed_common_properties, "assembly_role": "front_double_door"},
    )
    builder.add_box(
        "shed",
        "ShedSideServiceDoor",
        1 * INCH,
        cfg.SHED_SIDE_DOOR_WIDTH,
        cfg.SHED_SIDE_DOOR_HEIGHT,
        shed_x + cfg.SHED_WIDTH,
        side_door_y,
        ZERO,
        cfg.SHED_TRIM_COLOR,
        parent_id=shed_parent_id,
        properties={**shed_common_properties, "assembly_role": "side_service_door"},
    )

    # Fill the narrow landscape strip between the shed's right wall and the
    # unified grass at x=0 with rock, while leaving the front paver drive intact.
    rock_bed_x = shed_x + cfg.SHED_WIDTH
    rock_bed_width = ZERO - rock_bed_x
    builder.add_box(
        "site",
        "ShedGrassRockBed",
        rock_bed_width,
        cfg.SHED_DEPTH,
        cfg.ROCK_BED_THICKNESS,
        rock_bed_x,
        shed_y,
        -cfg.ROCK_BED_THICKNESS,
        cfg.ROCK_COLOR,
        drawing_label=True,
        properties={
            "complex_type": "landscape_rock_bed",
            "assembly_role": "transition_between_shed_and_grass",
            "from_element_id": "complex.shed.yard_storage_shed",
            "to_element_id": "complex.site.unified_yard_grass",
            "surface": "landscape_rock",
        },
    )
    # Deterministic accent stones break up the otherwise planar rock-bed
    # surface without introducing external mesh assets.
    for rock_index in range(12):
        rock_radius = (2.5 + (rock_index % 4) * 0.45) * INCH
        rock_x = rock_bed_x + rock_bed_width * ((rock_index % 3) + 1) / 4
        rock_y = shed_y + cfg.SHED_DEPTH * ((rock_index // 3) + 1) / 5
        rock_shape = (
            Sphere(to_mm(rock_radius)).solid().translate((to_mm(rock_x), to_mm(rock_y), -to_mm(rock_radius) * 0.25))
        )
        builder.add_shape(
            "site",
            f"ShedRockAccent_{rock_index + 1:02d}",
            rock_shape,
            cfg.ROCK_COLOR,
            Dimensions(to_mm(2 * rock_radius), to_mm(2 * rock_radius), to_mm(2 * rock_radius)),
            placement=(rock_x - rock_radius, rock_y - rock_radius, -rock_radius),
            parent_id="complex.site.shed_grass_rock_bed",
            properties={
                "complex_type": "landscape_accent_stone",
                "assembly_role": "rock_bed_surface_detail",
            },
        )

    # Evergreen screen along x=0. Tree_06 is intentionally removed to form the
    # 10ft vehicle opening beside the pool; the two bordering trees are clipped
    # in depth at the opening, and Tree_11 extends the screen to the shed.
    _tree_trunk_height = cfg.TREE_TRUNK_HEIGHT
    _tree_trunk_radius = cfg.TREE_TRUNK_RADIUS
    _tree_layout = (
        (1, -24 * FOOT, 6 * FOOT),
        (2, -28 * FOOT, 6 * FOOT),
        (3, -32 * FOOT, 6 * FOOT),
        (4, -36 * FOOT, 6 * FOOT),
        (5, vehicle_connector_end_y + 1.5 * FOOT, 3 * FOOT),
        # Tree_06 removed for the vehicle opening.
        (7, vehicle_connector_start_y - 1.5 * FOOT, 3 * FOOT),
        (8, -58 * FOOT, 6 * FOOT),
        (9, -62 * FOOT, 6 * FOOT),
        (10, -66 * FOOT, 6 * FOOT),
        (11, -70 * FOOT, 6 * FOOT),
    )
    for tree_number, tree_y, lower_foliage_depth in _tree_layout:
        tree_z = ZERO
        # Trunk
        builder.add_cylinder(
            "site",
            f"Tree_{tree_number:02d}Trunk",
            (ZERO, tree_y, tree_z),
            (ZERO, tree_y, tree_z + _tree_trunk_height),
            _tree_trunk_radius,
            TREE_BROWN,
        )
        # Foliage: overlapping tapered cones create a natural evergreen crown
        # while remaining deterministic and lightweight enough for all exports.
        depth_scale = lower_foliage_depth / (6 * FOOT)
        height_variation = 1.0 + ((tree_number * 17) % 5 - 2) * 0.025
        _foliage_layers = [
            (3.0 * FOOT * depth_scale, 3.25 * FOOT * height_variation, ZERO),
            (2.35 * FOOT * depth_scale, 3.25 * FOOT * height_variation, 2.25 * FOOT),
            (1.65 * FOOT * depth_scale, 3.5 * FOOT * height_variation, 4.5 * FOOT),
        ]
        for layer_idx, (radius, height, z_offset) in enumerate(_foliage_layers):
            is_drawing_label = tree_number == 1 and layer_idx == 2  # label on top tier of first tree
            tree_shape = (
                Cone(to_mm(radius), to_mm(2 * INCH), to_mm(height))
                .solid()
                .translate((0.0, to_mm(tree_y), to_mm(tree_z + _tree_trunk_height + z_offset)))
            )
            builder.add_shape(
                "site",
                f"Tree_{tree_number:02d}Foliage_{layer_idx + 1}",
                tree_shape,
                TREE_GREEN,
                Dimensions(to_mm(2 * radius), to_mm(2 * radius), to_mm(height)),
                placement=(-radius, tree_y - radius, tree_z + _tree_trunk_height + z_offset),
                drawing_label=is_drawing_label,
                properties={
                    "complex_type": "evergreen_foliage_crown",
                    "assembly_role": "foliage",
                    "conceptual": False,
                },
            )

    # Positive-X evergreen line from the y=0 axis toward y=-14yd.  Retain an
    # exact 4ft pitch, stopping at the last center within the requested limit.
    _right_tree_count = (
        int(
            math.floor(
                to_mm(cfg.RIGHT_TREE_LINE_START_Y - cfg.RIGHT_TREE_LINE_END_Y) / to_mm(cfg.RIGHT_TREE_LINE_SPACING)
            )
        )
        + 1
    )
    for tree_index in range(_right_tree_count):
        tree_y = cfg.RIGHT_TREE_LINE_START_Y - tree_index * cfg.RIGHT_TREE_LINE_SPACING
        tree_number = tree_index + 1
        common_properties = {
            "complex_type": "evergreen_tree",
            "label": f"Right Yard Evergreen Tree {tree_number:02d}",
            "landscape_role": "positive_x_yard_tree_line",
            "layout_axis": "y",
            "center_x_mm": to_mm(cfg.RIGHT_TREE_LINE_X),
            "center_y_mm": to_mm(tree_y),
            "spacing_mm": to_mm(cfg.RIGHT_TREE_LINE_SPACING),
            "conceptual": False,
        }
        builder.add_cylinder(
            "site",
            f"RightBoundaryTree_{tree_number:02d}Trunk",
            (cfg.RIGHT_TREE_LINE_X, tree_y, ZERO),
            (cfg.RIGHT_TREE_LINE_X, tree_y, _tree_trunk_height),
            _tree_trunk_radius,
            TREE_BROWN,
            properties={**common_properties, "assembly_role": "trunk"},
        )
        height_variation = 1.0 + ((tree_number * 13) % 5 - 2) * 0.025
        for layer_idx, (radius, height, z_offset) in enumerate(
            [
                (3.0 * FOOT, 3.25 * FOOT * height_variation, ZERO),
                (2.35 * FOOT, 3.25 * FOOT * height_variation, 2.25 * FOOT),
                (1.65 * FOOT, 3.5 * FOOT * height_variation, 4.5 * FOOT),
            ]
        ):
            tree_shape = (
                Cone(to_mm(radius), to_mm(2 * INCH), to_mm(height))
                .solid()
                .translate((to_mm(cfg.RIGHT_TREE_LINE_X), to_mm(tree_y), to_mm(_tree_trunk_height + z_offset)))
            )
            builder.add_shape(
                "site",
                f"RightBoundaryTree_{tree_number:02d}Foliage_{layer_idx + 1}",
                tree_shape,
                TREE_GREEN,
                Dimensions(to_mm(2 * radius), to_mm(2 * radius), to_mm(height)),
                placement=(cfg.RIGHT_TREE_LINE_X - radius, tree_y - radius, _tree_trunk_height + z_offset),
                drawing_label=tree_number == 1 and layer_idx == 2,
                properties={
                    **common_properties,
                    "assembly_role": "foliage",
                    "foliage_tier": layer_idx + 1,
                },
            )
        if tree_number == 1:
            # A small cardinal branch tip preserves exact design/IFC bounds;
            # tessellated circular cones otherwise stop fractionally short of
            # their analytical radius in the IFC representation.
            builder.add_box(
                "site",
                "RightBoundaryTree_01CardinalBranchTip",
                1 * INCH,
                1 * INCH,
                1 * INCH,
                cfg.RIGHT_TREE_LINE_X - 0.5 * INCH,
                tree_y + 3 * FOOT - 1 * INCH,
                _tree_trunk_height + 2 * FOOT,
                TREE_GREEN,
                parent_id="complex.site.right_boundary_tree_01_foliage_1",
                properties={
                    **common_properties,
                    "complex_type": "evergreen_branch_tip",
                    "assembly_role": "cardinal_foliage_extent",
                },
            )

    rail_segment(
        "UpperFrontRail",
        (ZERO, -cfg.UPPER_DECK_DEPTH),
        (cfg.UPPER_DECK_WIDTH - post_thickness, -cfg.UPPER_DECK_DEPTH),
        cfg.UPPER_DECK_ELEVATION,
    )
    # StairSideRail connects UpperPost_R to UpperStraightLeftPost_Top
    rail_segment(
        "StairSideRail",
        (cfg.UPPER_DECK_WIDTH - post_thickness, -cfg.UPPER_DECK_DEPTH),
        (cfg.UPPER_DECK_WIDTH, upper_stair_start[1]),
        cfg.UPPER_DECK_ELEVATION,
    )
    rail_segment("LeftEdgeRail", (ZERO, -cfg.FIREPLACE_DEPTH), (ZERO, -cfg.UPPER_DECK_DEPTH), cfg.UPPER_DECK_ELEVATION)
    rail_segment(
        "LowerRightRail",
        (lower_x + cfg.LOWER_DECK_WIDTH, -cfg.LOWER_DECK_DEPTH),
        (lower_x + cfg.LOWER_DECK_WIDTH, ZERO),
        cfg.LOWER_DECK_ELEVATION,
    )
    rail_segment("LowerBackRail", (lower_x, ZERO), (lower_x + cfg.LOWER_DECK_WIDTH, ZERO), cfg.LOWER_DECK_ELEVATION)
    # LowerFrontRail not needed when stairs span the full deck width
    for name, post_x, post_y, post_z in [
        ("UpperPost_L", ZERO, -cfg.UPPER_DECK_DEPTH, cfg.UPPER_DECK_ELEVATION),
        ("UpperPost_R", cfg.UPPER_DECK_WIDTH - post_thickness, -cfg.UPPER_DECK_DEPTH, cfg.UPPER_DECK_ELEVATION),
        ("LowerPost_LH", lower_x, ZERO, cfg.LOWER_DECK_ELEVATION),
        ("LowerPost_RH", lower_x + cfg.LOWER_DECK_WIDTH, ZERO, cfg.LOWER_DECK_ELEVATION),
        ("LowerPost_RF", lower_x + cfg.LOWER_DECK_WIDTH, -cfg.LOWER_DECK_DEPTH, cfg.LOWER_DECK_ELEVATION),
    ]:
        rail_post(name, post_x, post_y, post_z)

    # LowerDeckFrontLeftCornerPost was removed — the lower stair run's left
    # handrail/posts were shifted 6in left instead (see above).

    return DesignModel(
        id="file.template",
        name=cfg.PROJECT_NAME,
        artifact_stem="FileTemplate",
        elements=builder.elements,
        metadata={
            "project": "File Template CAD",
            "source_authority": "https://github.com/brandon-benge/benge-property-cad",
            "source_commit": context.source_revision or "unknown",
        },
    )
