# Floor-plan pipeline

Turns an iPhone capture of a property into a dimensioned, stitched floor plan with openings,
damage regions, concealed-damage flags, scope line items and a confidence interval on every
measurement. Three input tiers: photos, video, LiDAR.

This is a submission for the Applied AI Engineer case study. The brief is in
[spec/case_study.md](spec/case_study.md).

## Status

Work in progress. [COMPLIANCE.md](COMPLIANCE.md) lists every requirement with its current,
honest status. [docs/JOURNAL.md](docs/JOURNAL.md) records what was done and when.

## Where things are

| Path | Contents |
|---|---|
| `spec/` | The brief, the Round 1 gate table and the output schema |
| `COMPLIANCE.md` | Requirement → file path → artifact → status |
| `docs/decisions/` | Design decisions and the reasons for them |
| `docs/JOURNAL.md` | Dated work log |

Setup and run instructions are added here as soon as there is something to run.

## Use of AI tools

The brief allows AI coding tools. Claude Code was used throughout; commits it helped write
carry a `Co-Authored-By` trailer.
