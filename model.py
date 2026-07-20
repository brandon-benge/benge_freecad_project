"""Headless shared-model translation of the linked File Template CAD concept."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from build123d import Plane
from python_cad_tools.context import BuildContext
from python_cad_tools.elements import DesignElement, DesignModel, Dimensions, IfcMapping, MaterialSpec, Placement
from python_cad_tools.geometry import box, cylinder_between, prism_between, sloped_pool
from python_cad_tools.units import INCH, MM, Length, mm, to_mm

import config as cfg

ZERO = 0 * MM
Color = tuple[float, float, float]
Point3 = tuple[Length, Length, Length]
Point2 = tuple[Length, Length]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()).strip("_")


# Human-readable material names and densities (kg/m³) keyed by (category, color_rgb).
# Each entry: human_readable_name, density_kg_m3
# Material IDs (generated from category + rounded RGB) remain stable for backward compatibility.
MATERIAL_REGISTRY: dict[tuple[str, Color], tuple[str, float]] = {
    # Deck
    ("deck-board", cfg.DECK_COLOR): ("Composite Decking", 700.0),
    ("deck-framing", cfg.SKIRTING_COLOR): ("Pressure-Treated Lumber", 500.0),
    ("deck-framing", cfg.RAILING_COLOR): ("Pressure-Treated Lumber", 500.0),
    # Roof
    ("roof", cfg.RAILING_COLOR): ("Roof Fascia Assembly", 500.0),
    ("roof", (0.18, 0.20, 0.22)): ("Roof Cover Assembly", 50.0),
    ("roof-framing", (0.92, 0.92, 0.90)): ("Dimensional Lumber", 500.0),
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
    # Skirting
    ("skirting", cfg.SKIRTING_COLOR): ("Pressure-Treated Skirting", 500.0),
    # Stair
    ("stair", cfg.DECK_COLOR): ("Composite Tread", 700.0),
    ("stair", cfg.SKIRTING_COLOR): ("Framing Lumber", 500.0),
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
    ) -> DesignElement:
        stable_id = f"complex.{_slug(category)}.{_slug(name)}"
        values = dict(properties or {})
        if drawing_label:
            values["drawing_label"] = True
        element = DesignElement(
            id=stable_id,
            name=name,
            category=category,
            geometry=shape,
            geometry_kind="solid",
            placement=Placement((to_mm(placement[0]), to_mm(placement[1]), to_mm(placement[2]))),
            dimensions=dimensions,
            material=self.material(category, color),
            color_rgb=color,
            ifc_mapping=IfcMapping("IfcBuildingElementProxy", "NOTDEFINED"),
            storey="Exterior Concept",
            tags={"file-template", _slug(category)},
            properties=values,
            source_module="model",
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
        )

    def add_cylinder(
        self,
        category: str,
        name: str,
        start: Point3,
        end: Point3,
        radius: Length,
        color: Color,
    ) -> DesignElement:
        length = math.dist(tuple(to_mm(value) for value in start), tuple(to_mm(value) for value in end))
        return self.add_shape(
            category,
            name,
            cylinder_between(start, end, radius),
            color,
            Dimensions(length_mm=length, radius_mm=to_mm(radius)),
            placement=start,
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
    ) -> DesignElement:
        length = math.dist(tuple(to_mm(value) for value in start), tuple(to_mm(value) for value in end))
        return self.add_shape(
            category,
            name,
            prism_between(start, end, width, height),
            color,
            Dimensions(length, to_mm(width), to_mm(height)),
            placement=start,
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
        prefix: str, x: Length, y: Length, length: Length, depth: Length, z: Length, post_points: list[Point2]
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
            builder.add_box(
                "deck-framing",
                f"{prefix}MidBeam",
                length,
                cfg.BEAM_WIDTH,
                cfg.BEAM_HEIGHT,
                x,
                y + depth / 2 - cfg.BEAM_WIDTH / 2,
                beam_z,
                cfg.RAILING_COLOR,
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

    builder.add_box(
        "house",
        "HouseMass",
        cfg.HOUSE_WIDTH,
        cfg.HOUSE_DEPTH,
        cfg.HOUSE_HEIGHT,
        ZERO,
        ZERO,
        ZERO,
        cfg.HOUSE_COLOR,
        drawing_label=True,
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
    )

    lower_x = cfg.UPPER_DECK_WIDTH
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
            (lower_x + cfg.LOWER_DECK_WIDTH, -cfg.LOWER_DECK_DEPTH / 2),
        ],
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
    builder.add_box(
        "feature",
        "CoveredDeckFanBlade_X_Pos",
        blade,
        cfg.FAN_BLADE_WIDTH,
        INCH,
        fan_x,
        fan_y - cfg.FAN_BLADE_WIDTH / 2,
        fan_z,
        cfg.SKIRTING_COLOR,
    )
    builder.add_box(
        "feature",
        "CoveredDeckFanBlade_X_Neg",
        blade,
        cfg.FAN_BLADE_WIDTH,
        INCH,
        fan_x - blade,
        fan_y - cfg.FAN_BLADE_WIDTH / 2,
        fan_z,
        cfg.SKIRTING_COLOR,
    )
    builder.add_box(
        "feature",
        "CoveredDeckFanBlade_Y_Pos",
        cfg.FAN_BLADE_WIDTH,
        blade,
        INCH,
        fan_x - cfg.FAN_BLADE_WIDTH / 2,
        fan_y,
        fan_z,
        cfg.SKIRTING_COLOR,
    )
    builder.add_box(
        "feature",
        "CoveredDeckFanBlade_Y_Neg",
        cfg.FAN_BLADE_WIDTH,
        blade,
        INCH,
        fan_x - cfg.FAN_BLADE_WIDTH / 2,
        fan_y - blade,
        fan_z,
        cfg.SKIRTING_COLOR,
    )

    builder.add_box(
        "fireplace",
        "FireplaceMasonryBody",
        cfg.FIREPLACE_WIDTH,
        cfg.FIREPLACE_DEPTH,
        cfg.FIREPLACE_HEIGHT,
        ZERO,
        -cfg.FIREPLACE_DEPTH,
        ZERO,
        cfg.BRICK_COLOR,
        drawing_label=True,
    )
    fireplace_face_x = cfg.FIREPLACE_WIDTH
    fireplace_center_y = -cfg.FIREPLACE_DEPTH / 2
    builder.add_box(
        "fireplace",
        "FireplaceOpening",
        INCH,
        cfg.FIREPLACE_OPENING_WIDTH,
        cfg.FIREPLACE_OPENING_HEIGHT,
        fireplace_face_x,
        fireplace_center_y - cfg.FIREPLACE_OPENING_WIDTH / 2,
        cfg.UPPER_DECK_ELEVATION + 12 * INCH,
        (0.03, 0.03, 0.03),
    )
    builder.add_box(
        "fireplace",
        "ElectricFireplaceGlow",
        1.5 * INCH,
        cfg.FIREPLACE_OPENING_WIDTH - 4 * INCH,
        cfg.FIREPLACE_OPENING_HEIGHT - 6 * INCH,
        fireplace_face_x + INCH,
        fireplace_center_y - (cfg.FIREPLACE_OPENING_WIDTH - 4 * INCH) / 2,
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
    builder.add_box(
        "feature",
        "SlidingDoor",
        cfg.DOOR_WIDTH,
        3 * INCH,
        cfg.DOOR_HEIGHT,
        3 * cfg.FOOT,
        -1.5 * INCH,
        cfg.UPPER_DECK_ELEVATION,
        (0.55, 0.70, 0.82),
        drawing_label=True,
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
    builder.add_box(
        "outdoor-kitchen",
        "OutdoorKitchenCountertop",
        cfg.KITCHEN_LENGTH + 4 * INCH,
        cfg.KITCHEN_DEPTH + 4 * INCH,
        cfg.KITCHEN_COUNTER_THICKNESS,
        kitchen_x - 2 * INCH,
        kitchen_y - 2 * INCH,
        cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT - cfg.KITCHEN_COUNTER_THICKNESS,
        (0.45, 0.45, 0.42),
    )
    sink_x = kitchen_x + 18 * INCH
    sink_y = kitchen_y + (cfg.KITCHEN_DEPTH - cfg.KITCHEN_SINK_DEPTH) / 2
    builder.add_box(
        "outdoor-kitchen",
        "OutdoorKitchenSinkBasin",
        cfg.KITCHEN_SINK_WIDTH,
        cfg.KITCHEN_SINK_DEPTH,
        5 * INCH,
        sink_x,
        sink_y,
        cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT - 5 * INCH,
        (0.12, 0.15, 0.16),
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
    builder.add_box(
        "outdoor-kitchen",
        "OutdoorKitchenGrill",
        cfg.KITCHEN_GRILL_WIDTH,
        cfg.KITCHEN_DEPTH + 2 * INCH,
        8 * INCH,
        kitchen_x + cfg.KITCHEN_LENGTH - cfg.KITCHEN_GRILL_WIDTH - 12 * INCH,
        kitchen_y - INCH,
        cfg.UPPER_DECK_ELEVATION + cfg.KITCHEN_COUNTER_HEIGHT,
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

    hot_tub_x = cfg.UPPER_DECK_WIDTH + cfg.LOWER_DECK_WIDTH - cfg.HOT_TUB_WIDTH - cfg.FOOT
    hot_tub_y = -13 * cfg.FOOT
    builder.add_box(
        "feature",
        "HotTubPlaceholder",
        cfg.HOT_TUB_WIDTH,
        cfg.HOT_TUB_DEPTH,
        cfg.HOT_TUB_ABOVE_DECK,
        hot_tub_x,
        hot_tub_y,
        cfg.LOWER_DECK_ELEVATION,
        (0.08, 0.10, 0.12),
        drawing_label=True,
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

    rail_height = 42 * INCH
    rail_thickness = 2 * INCH
    post_thickness = 4 * INCH

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
        prefix: str, start: Point2, end: Point2, start_z: Length, end_z: Length, width: Length = cfg.STAIR_WIDTH
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
            # Place the tread board so its top (walking surface) is at tread_z,
            # matching the deck-board convention.  Previously the board bottom
            # sat at tread_z, which left the riser (spanning tread_z upward)
            # passing through the tread surface instead of lining up with the
            # back of the step.
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

            # Put the riser/backboard at the rear edge of the tread (toward
            # the upper landing).  It was previously centered on the tread,
            # which made it visibly pass through the walking surface.  With the
            # tread top now at tread_z, the riser sits on top of the tread's
            # back edge and rises to the landing/previous tread walking surface.
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
            offset = side_sign * rail_offset
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
            skirt_start_x = mm(to_mm(start[0]) + px * side_sign * skirt_offset)
            skirt_start_y = mm(to_mm(start[1]) + py * side_sign * skirt_offset)
            skirt_end_x = mm(to_mm(end[0]) + px * side_sign * skirt_offset)
            skirt_end_y = mm(to_mm(end[1]) + py * side_sign * skirt_offset)
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
    builder.add_box(
        "skirting",
        "UpperDeckLeftSkirt",
        skirt_thickness,
        cfg.UPPER_DECK_DEPTH,
        upper_skirt_height,
        -skirt_thickness,
        -cfg.UPPER_DECK_DEPTH,
        ZERO,
        cfg.SKIRTING_COLOR,
    )
    builder.add_box(
        "skirting",
        "UpperDeckRightSkirt",
        skirt_thickness,
        cfg.UPPER_DECK_DEPTH,
        upper_skirt_height,
        cfg.UPPER_DECK_WIDTH,
        -cfg.UPPER_DECK_DEPTH,
        ZERO,
        cfg.SKIRTING_COLOR,
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

    upper_stair_start = (cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH / 2, -6 * cfg.FOOT)
    upper_stair_end = (upper_stair_start[0], -6 * cfg.FOOT - 44 * INCH)
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
        upper_skirt_height,
        cfg.UPPER_DECK_WIDTH + cfg.STAIR_WIDTH,
        -6 * cfg.FOOT,
        ZERO,
        cfg.SKIRTING_COLOR,
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

    # Change 3: Lower deck stairs span full X-axis width of the lower deck
    lower_stair_width = cfg.LOWER_DECK_WIDTH
    lower_stair_start = (lower_x + lower_stair_width / 2, -cfg.LOWER_DECK_DEPTH)
    lower_stair_end = (lower_stair_start[0], -cfg.LOWER_DECK_DEPTH - 55 * INCH)
    stair_run("LowerFront", lower_stair_start, lower_stair_end, cfg.LOWER_DECK_ELEVATION, ZERO, lower_stair_width)
    # No LowerDeckFrontSkirt needed when stairs span the full deck width

    pool_y = -(cfg.LOWER_DECK_DEPTH + 7 * cfg.FOOT + 6 * cfg.FOOT + 15 * cfg.FOOT)
    pool_length = cfg.POOL_LENGTH
    pool_width = cfg.POOL_WIDTH
    # The pool and its right tile border extend to the right edge of the lower
    # deck on the x axis.  The right tile border is the rightmost element, so
    # its right edge aligns with the lower deck right edge; the pool sits just
    # inside it.
    lower_deck_right_x = cfg.UPPER_DECK_WIDTH + cfg.LOWER_DECK_WIDTH
    pool_right_x = lower_deck_right_x - cfg.PATIO_BORDER
    pool_x = pool_right_x - pool_length
    # 2' tile ground border around the pool.  Modeled as a ring of individual
    # 2' x 2' tile solids (not a single solid slab) so the pool surround reads
    # as laid tile rather than a monolithic pour.  The left/right strips span
    # the full width including corners; the near/far strips fill the gap
    # between them so no tile overlaps the pool footprint or another tile.
    tile_border = cfg.PATIO_BORDER
    tile_size = cfg.POOL_TILE_SIZE
    tile_thickness = 4 * INCH
    tile_z = -tile_thickness

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

    # Grass strip between the lower deck stairs and the pool's near tile
    # border, spanning the pool surround x footprint.
    lower_stair_end_y = -cfg.LOWER_DECK_DEPTH - 55 * INCH
    grass_near_y = lower_stair_end_y
    grass_far_y = pool_y + pool_width + tile_border
    grass_x = pool_x - tile_border
    grass_length = lower_deck_right_x - grass_x
    grass_depth = grass_near_y - grass_far_y
    if to_mm(grass_depth) > 0:
        builder.add_box(
            "site",
            "PoolGrassStrip",
            grass_length,
            grass_depth,
            cfg.GRASS_THICKNESS,
            grass_x,
            grass_far_y,
            -cfg.GRASS_THICKNESS,
            cfg.GRASS_COLOR,
            drawing_label=True,
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
    builder.add_shape(
        "pool",
        "PoolWater_34x12_5ftTo8ft",
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
            "quantity_provenance": "exact_sloped_geometry",
            "deep_end_side": cfg.POOL_DEEP_END_SIDE,
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

    # Horizontal cylindrical rail connecting LowerFrontLeftPost_Top (Z=1879.6) to UpperPost_R side
    rail_z = cfg.LOWER_DECK_ELEVATION + rail_height  # 32*INCH + 42*INCH = 74*INCH = 1879.6mm
    builder.add_cylinder(
        "railing",
        "LowerFrontLeftToUpperRRail",
        (cfg.UPPER_DECK_WIDTH, -cfg.LOWER_DECK_DEPTH, rail_z),
        (cfg.UPPER_DECK_WIDTH - post_thickness, -cfg.UPPER_DECK_DEPTH, rail_z),
        rail_thickness,
        cfg.RAILING_COLOR,
    )

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
