"""The output contract: a confidence interval on every measurement in plan.json.

The brief asks for an interval on every measurement. This walks the whole serialised plan and
checks every measurement-shaped object: either a value with a 90% interval around it, or
explicitly not measured, never a bare number dressed as a measurement.
"""

import json

from floorplan.output.serialize import plan_to_dict


def _measurements(node, path="plan"):
    """Every dict in the tree that carries a measured value."""
    if isinstance(node, dict):
        if "value" in node and "basis" in node:
            yield path, node
        for key, child in node.items():
            yield from _measurements(child, f"{path}.{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from _measurements(child, f"{path}[{index}]")


def _check(plan_dict):
    found = list(_measurements(plan_dict))
    assert found, "no measurements found"
    for path, m in found:
        assert m["coverage"] == 0.9, path
        if m["basis"] == "not_measured":
            assert m["value"] is None and m["lo"] is None and m["hi"] is None, path
            continue
        assert m["basis"] in ("observed", "inferred"), path
        assert m["lo"] is not None and m["hi"] is not None, path
        assert m["lo"] <= m["value"] <= m["hi"], path
        if m.get("unit") == "each":  # a count of items (one inspection) is exact, not measured
            assert float(m["value"]).is_integer(), path
            continue
        assert m["hi"] > m["lo"], f"{path}: a zero-width interval claims certainty"
    return found


def test_every_measurement_of_a_multi_room_plan_has_an_interval(flat_plan):
    plan = json.loads(json.dumps(plan_to_dict(flat_plan, "flat")))  # exactly what is written
    found = _check(plan)
    kinds = {path.split(".")[-1] for path, _ in found}
    # walls, areas, heights and openings are all covered, not just some of them
    assert {"length", "floor_area", "ceiling_height", "width", "footprint_area"} <= kinds


def test_the_plan_states_the_contract_it_follows(box_room_plan):
    plan = json.loads(json.dumps(plan_to_dict(box_room_plan, "box_room")))
    _check(plan)
    for key in ("damage_regions", "concealed_damage_flags", "scope_items", "warnings"):
        assert key in plan
    assert plan["intervals"]["coverage"] == 0.9
