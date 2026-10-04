"""Every plan.json follows schema/plan.schema.json and is strict JSON.

No schema was supplied with the brief, so we publish our own. These tests keep it and the
writer in step: a field added to the writer but not to the schema (or the other way round)
fails here. Plans are dumped with `allow_nan=False`, the way a strict reader parses them: a
NaN that slipped through would be written as `NaN`, which is not JSON.
"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from floorplan.output.serialize import plan_to_dict
from floorplan.synth.render import pose
from floorplan.uncertainty.budget import Measurement

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "plan.schema.json").read_text())
SAMPLE_PLANS = sorted((ROOT / "reports" / "samples").rglob("plan.json"))


def _validate(plan_dict: dict) -> None:
    written = json.loads(json.dumps(plan_dict, allow_nan=False))  # exactly what a reader sees
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(written), key=str)
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


def test_the_schema_itself_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


def test_a_multi_room_plan_follows_the_schema(flat_plan):
    _validate(plan_to_dict(flat_plan, "flat"))


def test_a_plan_with_damage_flags_and_scope_follows_the_schema(box_room_plan):
    from test_semantics import _run

    corners = np.array([[4.2, 1.0, 0.1], [4.2, 1.6, 0.1], [4.2, 1.6, 0.5], [4.2, 1.0, 0.5]])
    view = pose(2.1, 1.3, 1.4, 0.0, np.radians(-25.0))
    plan, regions, flags, scope = _run(box_room_plan, view, "water stain", corners)
    assert regions and flags and scope
    _validate(plan_to_dict(replace(plan, damage=regions, flags=flags, scope=scope), "box_room"))


def test_a_room_without_a_ceiling_is_still_strict_json(box_room_plan):
    # the photo tier gives (nan, nan) as the range when no photo showed the ceiling
    room = replace(
        box_room_plan.rooms[0],
        ceiling_height=Measurement(float("nan"), 0.0, "inferred"),
        ceiling_height_range=(float("nan"), float("nan")),
    )
    written = plan_to_dict(replace(box_room_plan, rooms=[room]), "no_ceiling")
    assert written["rooms"][0]["ceiling_height_range"] is None
    _validate(written)


@pytest.mark.parametrize(
    "path",
    SAMPLE_PLANS,
    ids=[str(p.parent.relative_to(ROOT / "reports" / "samples")) for p in SAMPLE_PLANS],
)
def test_the_supplied_sample_plans_follow_the_schema(path):
    text = path.read_text()
    assert "NaN" not in text and "Infinity" not in text
    _validate(json.loads(text))
