"""Score plans against ground truth and evaluate the gates, each exactly as the brief words it.

Input is only what a run writes (`plan.json`, `run_log.json`) and the ground-truth files.
Nothing here imports the pipeline, so the scorer cannot be bent toward its output, and a fix
to the pipeline can never be a change to this file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
from shapely.geometry import Polygon

from truth import Prediction, Truth, match_openings, match_rooms

# Gate thresholds, from spec/case_study.md
OPENING_WIDTH_TOLERANCE = 0.02  # metres
OPENING_PASS_SHARE = 0.85
CEILING_TOLERANCE = 0.015
CEILING_REPEAT_SPREAD = 0.01
REPEAT_ABSOLUTE = 0.01
REPEAT_RELATIVE = 0.005
WALL_RELATIVE = {"photo": 0.08, "video": 0.03}  # the LiDAR wall gate comes from Round 1
FOOTPRINT_RELATIVE = 0.08
OVERLAP_TOLERANCE = 0.01  # m2
NOMINAL_COVERAGE = 0.90


@dataclass
class Row:
    """One measured quantity compared with its ground truth."""

    capture: str
    tier: str
    kind: str  # wall_length | ceiling_height | opening_width | floor_area | footprint_area
    id: str
    truth: float
    value: float | None
    lo: float | None
    hi: float | None
    basis: str | None

    @property
    def error(self) -> float | None:
        return None if self.value is None else self.value - self.truth

    @property
    def covered(self) -> bool | None:
        if self.value is None or self.lo is None:
            return None
        return self.lo <= self.truth <= self.hi

    def to_dict(self) -> dict:
        data = asdict(self)
        data["error"] = None if self.error is None else round(self.error, 4)
        data["covered"] = self.covered
        return data


@dataclass
class CaptureScore:
    capture: str
    tier: str
    site: str
    group: str | None
    rows: list[Row] = field(default_factory=list)
    openings: list[dict] = field(default_factory=list)  # one per measured or phantom opening
    rooms_measured: int = 0
    rooms_found: int = 0
    rooms_with_wrong_wall_count: list[str] = field(default_factory=list)
    adjacency_correct: bool = False
    adjacency_detail: dict = field(default_factory=dict)
    overlap_area: float = 0.0
    timings: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _row(capture, tier, kind, identifier, truth_value, measurement) -> Row:
    if measurement is None or measurement.get("value") is None:
        return Row(capture, tier, kind, identifier, float(truth_value), None, None, None, None)
    return Row(
        capture,
        tier,
        kind,
        identifier,
        float(truth_value),
        float(measurement["value"]),
        float(measurement["lo"]),
        float(measurement["hi"]),
        measurement.get("basis"),
    )


def score_capture(
    capture: str,
    truth: Truth,
    prediction: Prediction,
    group: str | None = None,
    run_log: dict | None = None,
) -> CaptureScore:
    tier = prediction.tier
    score = CaptureScore(capture, tier, truth.site, group)
    score.rooms_measured = len(truth.rooms)
    score.rooms_found = len(prediction.rooms)
    score.timings = (run_log or {}).get("timings_s", {})
    score.warnings = list(prediction.raw.get("warnings", []))

    matches = match_rooms(truth, prediction)
    name_of: dict[str, str] = {}  # predicted room id -> measured room id
    for match in matches:
        room = match.truth
        if match.predicted is None:
            for index, length in enumerate(room.walls):
                score.rows.append(
                    _row(
                        capture,
                        tier,
                        "wall_length",
                        f"{room.id}-{room.wall_ids[index]}",
                        length,
                        None,
                    )
                )
            if room.ceiling_height is not None:
                score.rows.append(
                    _row(capture, tier, "ceiling_height", room.id, room.ceiling_height, None)
                )
            continue
        name_of[match.predicted.id] = room.id
        if not match.wall_count_matches:
            score.rooms_with_wrong_wall_count.append(room.id)
        for index, length in enumerate(room.walls):
            wall = match.predicted_wall(index)
            measurement = None if wall is None else match.predicted.walls[wall]
            score.rows.append(
                _row(
                    capture,
                    tier,
                    "wall_length",
                    f"{room.id}-{room.wall_ids[index]}",
                    length,
                    measurement,
                )
            )
        if room.ceiling_height is not None:
            score.rows.append(
                _row(
                    capture,
                    tier,
                    "ceiling_height",
                    room.id,
                    room.ceiling_height,
                    match.predicted.ceiling_height,
                )
            )
        if room.floor_area is not None:
            score.rows.append(
                _row(
                    capture,
                    tier,
                    "floor_area",
                    room.id,
                    room.floor_area,
                    match.predicted.floor_area,
                )
            )

    for pair in match_openings(matches, prediction):
        if pair.truth is not None and pair.predicted is not None:
            row = _row(
                capture,
                tier,
                "opening_width",
                pair.truth.id,
                pair.truth.width,
                pair.predicted.width,
            )
            score.rows.append(row)
            score.openings.append(
                {
                    "id": pair.truth.id,
                    "outcome": "matched",
                    "predicted": pair.predicted.id,
                    "truth_kind": pair.truth.kind,
                    "predicted_kind": pair.predicted.kind,
                    "width_error": round(row.error, 4),
                    "within_tolerance": abs(row.error) <= OPENING_WIDTH_TOLERANCE,
                }
            )
        elif pair.truth is not None:
            score.openings.append(
                {
                    "id": pair.truth.id,
                    "outcome": "missed",
                    "truth_kind": pair.truth.kind,
                    "within_tolerance": False,
                }
            )
        else:
            score.openings.append(
                {
                    "id": pair.predicted.id,
                    "outcome": "phantom",
                    "predicted_kind": pair.predicted.kind,
                    "within_tolerance": False,
                }
            )

    if truth.footprint_area is not None:
        score.rows.append(
            _row(
                capture,
                tier,
                "footprint_area",
                truth.site,
                truth.footprint_area,
                prediction.footprint_area,
            )
        )

    found = sorted(
        {tuple(sorted(name_of.get(r, f"?{r}") for r in pair)) for pair in prediction.adjacency}
    )
    wanted = sorted(set(truth.adjacency))
    score.adjacency_correct = found == wanted and score.rooms_found == score.rooms_measured
    score.adjacency_detail = {"measured": wanted, "found": found}

    polygons = [Polygon(room.polygon) for room in prediction.rooms]
    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            if polygons[i].is_valid and polygons[j].is_valid:
                score.overlap_area += float(polygons[i].intersection(polygons[j]).area)
    return score


# ------------------------------------------------------------------------ gates


def _gate(
    name: str, tier: str, passed: bool | None, value: str, threshold: str, detail: str = ""
) -> dict:
    status = "not evaluated" if passed is None else ("PASS" if passed else "FAIL")
    return {
        "gate": name,
        "tier": tier,
        "status": status,
        "value": value,
        "threshold": threshold,
        "detail": detail,
    }


def _rows(scores: list[CaptureScore], kind: str) -> list[Row]:
    return [row for score in scores for row in score.rows if row.kind == kind]


def opening_gate(scores: list[CaptureScore], tier: str) -> dict:
    outcomes = [o for score in scores for o in score.openings]
    if not outcomes:
        return _gate("Opening widths", tier, None, "no openings measured", "")
    passed = sum(o["within_tolerance"] for o in outcomes)
    share = passed / len(outcomes)
    missed = sum(o["outcome"] == "missed" for o in outcomes)
    phantom = sum(o["outcome"] == "phantom" for o in outcomes)
    wide = sum(o["outcome"] == "matched" and not o["within_tolerance"] for o in outcomes)
    return _gate(
        "Opening widths",
        tier,
        share >= OPENING_PASS_SHARE,
        f"{passed}/{len(outcomes)} = {share:.0%}",
        "<= 2 cm on >= 85%; a miss and a phantom each count as a miss",
        f"{missed} missed, {phantom} phantom, {wide} found but off by more than 2 cm",
    )


def ceiling_gate(scores: list[CaptureScore], tier: str) -> dict:
    rows = _rows(scores, "ceiling_height")
    if not rows:
        return _gate("Ceiling height", tier, None, "no ceiling heights measured", "")
    errors = [abs(r.error) if r.error is not None else np.inf for r in rows]
    passed = sum(e <= CEILING_TOLERANCE for e in errors)
    finite = [e for e in errors if np.isfinite(e)]
    worst = max(finite) if finite else float("nan")
    return _gate(
        "Ceiling height",
        tier,
        passed == len(rows),
        f"{passed}/{len(rows)} rooms within 1.5 cm; worst {worst * 100:.1f} cm",
        "<= 1.5 cm in every room",
        f"mean signed error {np.mean([r.error for r in rows if r.error is not None]) * 100:+.2f} cm"
        if finite
        else "",
    )


def _repeat_pairs(scores: list[CaptureScore], kind: str) -> list[tuple[Row, Row]]:
    groups: dict[str, list[CaptureScore]] = {}
    for score in scores:
        if score.group:
            groups.setdefault(score.group, []).append(score)
    pairs = []
    for members in groups.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                second = {r.id: r for r in members[j].rows if r.kind == kind}
                for row in members[i].rows:
                    if row.kind == kind and row.id in second:
                        pairs.append((row, second[row.id]))
    return pairs


def ceiling_repeat_gate(scores: list[CaptureScore], tier: str) -> dict:
    pairs = [
        (a, b)
        for a, b in _repeat_pairs(scores, "ceiling_height")
        if a.value is not None and b.value is not None
    ]
    if not pairs:
        return _gate(
            "Ceiling height, repeat captures", tier, None, "no room captured twice at this tier", ""
        )
    spreads = [abs(a.value - b.value) for a, b in pairs]
    bias = float(np.mean([(a.error + b.error) / 2 for a, b in pairs]))
    worst = max(spreads)
    unrepeatable = worst > CEILING_REPEAT_SPREAD
    biased = abs(bias) > CEILING_TOLERANCE
    verdict = (
        "unrepeatable"
        if unrepeatable
        else "repeatable but biased"
        if biased
        else "repeatable and unbiased"
    )
    return _gate(
        "Ceiling height, repeat captures",
        tier,
        not unrepeatable,
        f"spread {worst * 100:.2f} cm over {len(pairs)} room pair(s)",
        "spread across captures <= 1 cm",
        f"{verdict}; mean error {bias * 100:+.2f} cm",
    )


def repeatability_gate(scores: list[CaptureScore], tier: str) -> dict:
    pairs = [
        (a, b)
        for a, b in _repeat_pairs(scores, "wall_length")
        if a.value is not None and b.value is not None
    ]
    if not pairs:
        return _gate(
            "Repeatability per wall", tier, None, "no room captured twice at this tier", ""
        )
    differences = np.array([abs(a.value - b.value) for a, b in pairs])
    lengths = np.array([a.truth for a, _ in pairs])
    lenient = differences <= np.maximum(REPEAT_ABSOLUTE, REPEAT_RELATIVE * lengths)
    strict = differences <= np.minimum(REPEAT_ABSOLUTE, REPEAT_RELATIVE * lengths)
    return _gate(
        "Repeatability per wall",
        tier,
        bool(lenient.all()),
        f"{int(lenient.sum())}/{len(pairs)} walls agree; worst {differences.max() * 100:.2f} cm",
        "two captures agree within 1 cm or 0.5% per wall",
        f"reading 'or' as whichever is larger. Strict reading (whichever is smaller): "
        f"{int(strict.sum())}/{len(pairs)}",
    )


def wall_gate(scores: list[CaptureScore], tier: str) -> dict:
    rows = _rows(scores, "wall_length")
    if not rows:
        return _gate("Wall lengths", tier, None, "no walls measured", "")
    relative = np.array([abs(r.error) / r.truth if r.error is not None else np.inf for r in rows])
    finite = relative[np.isfinite(relative)]
    absolute = np.array([abs(r.error) for r in rows if r.error is not None])
    summary = (
        f"median {np.median(absolute) * 100:.1f} cm, worst {absolute.max() * 100:.1f} cm "
        f"({finite.max():.1%}); {int((~np.isfinite(relative)).sum())} wall(s) not found"
        if len(finite)
        else "no wall found"
    )
    if tier not in WALL_RELATIVE:
        return _gate(
            "Wall lengths", tier, None, summary, "set by the Round 1 gate table (not yet in spec/)"
        )
    limit = WALL_RELATIVE[tier]
    passed = int((relative <= limit).sum())
    return _gate(
        "Wall lengths",
        tier,
        passed == len(rows),
        f"{passed}/{len(rows)} within {limit:.0%}; {summary}",
        f"every wall within +-{limit:.0%}",
    )


def stitch_gate(scores: list[CaptureScore], tier: str) -> dict:
    multi = [s for s in scores if s.rooms_measured >= 3]
    if not multi:
        return _gate("Whole-property stitch", tier, None, "no multi-room capture at this tier", "")
    problems = []
    for score in multi:
        if score.rooms_found != score.rooms_measured:
            problems.append(
                f"{score.capture}: {score.rooms_found} rooms found, {score.rooms_measured} measured"
            )
        if not score.adjacency_correct:
            problems.append(
                f"{score.capture}: adjacency differs (found {score.adjacency_detail.get('found')})"
            )
        if score.overlap_area > OVERLAP_TOLERANCE:
            problems.append(f"{score.capture}: rooms overlap by {score.overlap_area:.2f} m2")
        for row in score.rows:
            if row.kind == "footprint_area":
                if row.error is None or abs(row.error) / row.truth > FOOTPRINT_RELATIVE:
                    problems.append(
                        f"{score.capture}: footprint off by "
                        f"{'n/a' if row.error is None else f'{row.error / row.truth:+.1%}'}"
                    )
                if row.covered is False:
                    problems.append(f"{score.capture}: footprint interval misses the truth")
    footprint = [
        r for s in multi for r in s.rows if r.kind == "footprint_area" and r.error is not None
    ]
    value = "; ".join(f"{r.capture}: footprint {r.error / r.truth:+.1%}" for r in footprint)
    return _gate(
        "Whole-property stitch",
        tier,
        not problems,
        value or "no footprint measured",
        "one plan, correct adjacency, no overlaps, footprint within +-8%, interval holds",
        "; ".join(problems),
    )


def calibration_gate(scores: list[CaptureScore], tier: str) -> dict:
    rows = [r for s in scores for r in s.rows if r.covered is not None]
    if not rows:
        return _gate("Interval calibration", tier, None, "no intervals to check", "")
    by_kind = {}
    for kind in sorted({r.kind for r in rows}):
        members = [r.covered for r in rows if r.kind == kind]
        by_kind[kind] = f"{sum(members)}/{len(members)}"
    covered = sum(r.covered for r in rows)
    share = covered / len(rows)
    # a 90% interval that holds 90% of the time: allow two standard errors of sampling noise
    slack = 2 * np.sqrt(NOMINAL_COVERAGE * (1 - NOMINAL_COVERAGE) / len(rows))
    return _gate(
        "Interval calibration",
        tier,
        share >= NOMINAL_COVERAGE - slack,
        f"{covered}/{len(rows)} = {share:.0%} of 90% intervals contain the truth",
        f">= {NOMINAL_COVERAGE - slack:.0%} (90% less two standard errors at n={len(rows)})",
        "; ".join(f"{kind} {value}" for kind, value in by_kind.items()),
    )


GATES = [
    opening_gate,
    ceiling_gate,
    ceiling_repeat_gate,
    repeatability_gate,
    wall_gate,
    stitch_gate,
    calibration_gate,
]


def evaluate(scores: list[CaptureScore]) -> list[dict]:
    """Every gate at every tier that has captures."""
    results = []
    for tier in ("lidar", "video", "photo"):
        members = [score for score in scores if score.tier == tier]
        if members:
            results.extend(gate(members, tier) for gate in GATES)
    return results
