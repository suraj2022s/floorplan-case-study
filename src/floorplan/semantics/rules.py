"""Concealed-damage flags, raised by the rules in `configs/rules.yaml`.

Kept deliberately plain: the rules are data, the code only checks conditions. A flag names
the rule that fired and the regions it fired on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from floorplan.pipeline import Plan
from floorplan.semantics.damage import DamageRegion

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Flag:
    id: str
    rule_id: str
    room: str
    surface: str
    damage_ids: list[str]
    message: str
    inspect: str | None  # scope catalogue item this flag asks for
    evidence: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "room": self.room,
            "surface": self.surface,
            "damage_regions": self.damage_ids,
            "message": self.message,
            "evidence": self.evidence,
        }


def load_rules(path: Path | None = None) -> list[dict]:
    return yaml.safe_load((path or ROOT / "configs" / "rules.yaml").read_text())["rules"]


def _fires(rule: dict, region: DamageRegion, plan: Plan) -> dict | None:
    """The evidence a rule fired on for a region, or None if it does not fire."""
    when = rule["when"]
    if region.kind not in when.get("classes", [region.kind]):
        return None
    if "surface" in when and region.surface_kind != when["surface"]:
        return None
    evidence: dict = {"class": region.kind, "surface_kind": region.surface_kind}
    room = next(r for r in plan.rooms if r.id == region.room)

    if "max_above_floor" in when:
        if region.above_floor > when["max_above_floor"]:
            return None
        evidence["lower_edge_above_floor_m"] = round(region.above_floor, 3)
    if "max_below_ceiling" in when:
        if not room.ceiling_height.available:
            return None
        gap = room.ceiling_height.value - (region.above_floor + region.height.value)
        if gap > when["max_below_ceiling"]:
            return None
        evidence["upper_edge_below_ceiling_m"] = round(gap, 3)
    if "min_area" in when:
        if region.area.value < when["min_area"]:
            return None
        evidence["bounding_area_m2"] = round(region.area.value, 3)
    if "near_opening" in when:
        near = when["near_opening"]
        left, right = region.along_surface, region.along_surface + region.width.value
        found = None
        for opening in plan.openings:
            if opening.wall != region.surface or opening.kind not in near["kinds"]:
                continue
            start = opening.position_along_wall
            end = start + opening.width.value
            gap = max(start - right, left - end, 0.0)
            if gap <= near["within"]:
                found = (opening.id, gap)
                break
        if found is None:
            return None
        evidence["opening"] = found[0]
        evidence["distance_to_opening_m"] = round(found[1], 3)
    return evidence


def raise_flags(
    plan: Plan, regions: list[DamageRegion], rules: list[dict] | None = None
) -> list[Flag]:
    rules = load_rules() if rules is None else rules
    flags = []
    for rule in rules:
        for region in regions:
            evidence = _fires(rule, region, plan)
            if evidence is not None:
                flags.append(
                    Flag(
                        id=f"FLAG{len(flags) + 1}",
                        rule_id=rule["id"],
                        room=region.room,
                        surface=region.surface,
                        damage_ids=[region.id],
                        message=" ".join(rule["message"].split()),
                        inspect=rule.get("inspect"),
                        evidence=evidence,
                    )
                )
    return flags
