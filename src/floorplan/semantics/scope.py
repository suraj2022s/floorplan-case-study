"""Scope line items, keyed to surfaces, from damage regions and flags.

The catalogue in `configs/scope_catalog.yaml` says which items a damage class calls for and
how each is quantified. Quantities are built from the plan's own measurements, so each one
carries an interval that follows from the intervals on the lengths behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from floorplan.pipeline import Plan
from floorplan.semantics.damage import DamageRegion
from floorplan.semantics.rules import Flag
from floorplan.uncertainty.budget import Measurement, quadrature

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class ScopeItem:
    id: str
    code: str
    description: str
    unit: str
    quantity: Measurement
    room: str
    surface: str
    damage_ids: list[str]
    rule_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "quantity": self.quantity.to_dict(),
            "room": self.room,
            "surface": self.surface,
            "damage_regions": self.damage_ids,
            "rule_id": self.rule_id,
        }


def _height(opening) -> Measurement:
    """An opening's height; door height, loosely, when its top was never seen."""
    if opening.height.available:
        return opening.height
    return Measurement(2.0, 0.2, "inferred")


def load_catalogue(path: Path | None = None) -> dict:
    return yaml.safe_load((path or ROOT / "configs" / "scope_catalog.yaml").read_text())


def surface_area(plan: Plan, surface: str) -> Measurement:
    """Paintable area of a wall (less its openings) or a ceiling."""
    for room in plan.rooms:
        if surface in (f"{room.id}-ceiling", f"{room.id}-floor"):
            return room.floor_area
        for wall in room.walls:
            if wall.id != surface:
                continue
            height = room.ceiling_height
            if not height.available:
                return Measurement(float("nan"), 0.0, unit="m2")
            gross = wall.length.value * height.value
            sigma = quadrature(height.value * wall.length.sigma, wall.length.value * height.sigma)
            openings = [o for o in plan.openings if o.wall == surface]
            cut = sum(o.width.value * _height(o).value for o in openings)
            cut_sigma = (
                quadrature(
                    *[
                        quadrature(
                            _height(o).value * o.width.sigma, o.width.value * _height(o).sigma
                        )
                        for o in openings
                    ]
                )
                if openings
                else 0.0
            )
            return Measurement(
                max(gross - cut, 0.0), quadrature(sigma, cut_sigma), wall.length.basis, unit="m2"
            )
    return Measurement(float("nan"), 0.0, unit="m2")


def build_scope(
    plan: Plan, regions: list[DamageRegion], flags: list[Flag], catalogue: dict | None = None
) -> list[ScopeItem]:
    catalogue = load_catalogue() if catalogue is None else catalogue
    items_spec = catalogue["items"]
    items: list[ScopeItem] = []
    repaint: dict[str, ScopeItem] = {}

    def add(
        code: str,
        quantity: Measurement,
        room: str,
        surface: str,
        damage: list[str],
        rule: str | None = None,
    ) -> ScopeItem:
        spec = items_spec[code]
        item = ScopeItem(
            f"S{len(items) + 1}",
            code,
            spec["description"],
            spec["unit"],
            quantity,
            room,
            surface,
            damage,
            rule,
        )
        items.append(item)
        return item

    for region in regions:
        for code in catalogue["by_class"].get(region.kind, []):
            if code == "REPAINT":
                if region.surface_kind == "floor":
                    continue
                if region.surface in repaint:  # one repaint per surface, however many regions
                    repaint[region.surface].damage_ids.append(region.id)
                    continue
                code = "REPAINT_CEILING" if region.surface_kind == "ceiling" else "REPAINT_WALL"
                repaint[region.surface] = add(
                    code,
                    surface_area(plan, region.surface),
                    region.room,
                    region.surface,
                    [region.id],
                )
                continue
            spec = items_spec[code]
            if spec["quantity"] == "damage_area":
                margin = spec.get("margin", 1.0)
                value = max(region.area.value * margin, spec.get("minimum", 0.0))
                quantity = Measurement(value, region.area.sigma * margin, unit="m2")
            elif spec["quantity"] == "damage_length":
                longer = (
                    region.width if region.width.value >= region.height.value else region.height
                )
                quantity = Measurement(longer.value, longer.sigma, unit="m")
            else:
                quantity = Measurement(1.0, 0.0, unit="each")
            add(code, quantity, region.room, region.surface, [region.id])

    inspections: dict[tuple[str, str], ScopeItem] = {}
    for flag in flags:
        if not flag.inspect:
            continue
        key = (flag.inspect, flag.surface)
        if key in inspections:  # one visit inspects the surface, however many rules ask for it
            ids = inspections[key].damage_ids
            ids.extend(i for i in flag.damage_ids if i not in ids)
            continue
        inspections[key] = add(
            flag.inspect,
            Measurement(1.0, 0.0, unit="each"),
            flag.room,
            flag.surface,
            list(flag.damage_ids),
            flag.rule_id,
        )
    return items
