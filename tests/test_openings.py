"""How an opening is named: door, window or passage."""

import numpy as np

from floorplan.geometry.openings import Opening, OpeningConfig, _merge_twins


def _half(room: str, other: str, top_seen: bool) -> Opening:
    """One room's view of a 0.9 m doorway, filmed low: the view stopped 1.4 m up."""
    return Opening(
        kind="door",
        room=room,
        edge=0,
        u0=1.0,
        u1=1.9,
        sill=0.0,
        height=1.4,
        width=0.9,
        width_sigma=0.03,
        method="jamb_faces",
        centre=np.array([1.45, 0.0]),
        open_share=0.9,
        other_room=other,
        wall_thickness=0.1,
        top_seen=top_seen,
    )


def test_a_doorway_seen_low_from_both_rooms_stays_a_door():
    # neither side saw the head of the doorway, so its 1.4 m "height" is where the view
    # stopped; merging the two sides must not turn it into a window standing on the floor
    merged = _merge_twins([_half("a", "b", False), _half("b", "a", False)], OpeningConfig())
    assert len(merged) == 1
    assert merged[0].kind == "door" and not merged[0].top_seen


def test_a_low_opening_whose_top_was_seen_is_a_window():
    merged = _merge_twins([_half("a", "b", True), _half("b", "a", False)], OpeningConfig())
    assert len(merged) == 1
    assert merged[0].kind == "window" and merged[0].top_seen
