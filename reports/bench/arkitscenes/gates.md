# Benchmark report: arkitscenes

Public data, used while no iPhone is available: one bedroom from Apple's ARKitScenes dataset, captured three times with the LiDAR of an iPad Pro (ARKit poses and depth) and scanned with a Faro laser. Ground truth is read off the laser scan (bench/ground_truth/arkitscenes-467138.yaml). This is real sensor data with laser ground truth, but it is not the benchmark set the brief specifies: one room only, no multi-room capture, no staged damage, an iPad rather than an iPhone, and captures made by Apple's operators rather than by following our protocol. Fetch with python scripts/fetch_arkitscenes.py.

## Gates

| Tier | Gate | Status | Result | Threshold | Notes |
|---|---|---|---|---|---|
| lidar | Opening widths | **FAIL** | 0/11 = 0% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 5 missed, 5 phantom, 1 found but off by more than 2 cm |
| lidar | Ceiling height | **FAIL** | 0/3 rooms within 1.5 cm; worst 3.6 cm | <= 1.5 cm in every room | mean signed error -3.19 cm |
| lidar | Ceiling height, repeat captures | **PASS** | spread 0.96 cm over 3 room pair(s) | spread across captures <= 1 cm | repeatable but biased; mean error -3.19 cm |
| lidar | Repeatability per wall | **not evaluated** | no room captured twice at this tier |  |  |
| lidar | Wall lengths | **not evaluated** | median 8.5 cm, worst 13.2 cm (4.1%); 8 wall(s) not found | set by the Round 1 gate table (not yet in spec/) |  |
| lidar | Whole-property stitch | **not evaluated** | no multi-room capture at this tier |  |  |
| lidar | Interval calibration | **FAIL** | 6/11 = 55% of 90% intervals contain the truth | >= 72% (90% less two standard errors at n=11) | ceiling_height 3/3; floor_area 1/3; opening_width 0/1; wall_length 2/4 |
| video | Opening widths | **FAIL** | 0/2 = 0% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 1 missed, 0 phantom, 1 found but off by more than 2 cm |
| video | Ceiling height | **FAIL** | 0/1 rooms within 1.5 cm; worst 18.7 cm | <= 1.5 cm in every room | mean signed error +18.66 cm |
| video | Ceiling height, repeat captures | **not evaluated** | no room captured twice at this tier |  |  |
| video | Repeatability per wall | **not evaluated** | no room captured twice at this tier |  |  |
| video | Wall lengths | **FAIL** | 2/4 within 3%; median 11.5 cm, worst 16.1 cm (5.0%); 0 wall(s) not found | every wall within +-3% |  |
| video | Whole-property stitch | **not evaluated** | no multi-room capture at this tier |  |  |
| video | Interval calibration | **PASS** | 6/7 = 86% of 90% intervals contain the truth | >= 67% (90% less two standard errors at n=7) | ceiling_height 1/1; floor_area 1/1; opening_width 0/1; wall_length 4/4 |

## Captures

| Capture | Tier | Rooms found / measured | Adjacency | Overlap (m²) | Time (s) |
|---|---|---|---|---|---|
| bedroom-a | lidar | 1 / 1 | correct | 0.000 | 13.0 |
| bedroom-b | lidar | 1 / 1 | correct | 0.000 | 6.8 |
| bedroom-c | lidar | 1 / 1 | correct | 0.000 | 10.6 |
| bedroom-a-video | video | 1 / 1 | correct | 0.000 | 40.0 |

## Wall lengths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom-W1 | 3.188 | 3.056 [2.974, 3.138] | -13.2 | NO |
| bedroom-a | bedroom-W2 | 3.721 | 3.709 [3.603, 3.816] | -1.2 | yes |
| bedroom-a | bedroom-W3 | 3.180 | 3.133 [1.898, 4.368] | -4.8 | yes |
| bedroom-a | bedroom-W4 | 3.728 | 3.605 [3.500, 3.711] | -12.3 | NO |
| bedroom-b | bedroom-W1 | 3.188 | not found | not found |  |
| bedroom-b | bedroom-W2 | 3.721 | not found | not found |  |
| bedroom-b | bedroom-W3 | 3.180 | not found | not found |  |
| bedroom-b | bedroom-W4 | 3.728 | not found | not found |  |
| bedroom-c | bedroom-W1 | 3.188 | not found | not found |  |
| bedroom-c | bedroom-W2 | 3.721 | not found | not found |  |
| bedroom-c | bedroom-W3 | 3.180 | not found | not found |  |
| bedroom-c | bedroom-W4 | 3.728 | not found | not found |  |
| bedroom-a-video | bedroom-W1 | 3.188 | 3.349 [3.055, 3.642] | +16.1 | yes |
| bedroom-a-video | bedroom-W2 | 3.721 | 3.783 [3.438, 4.129] | +6.2 | yes |
| bedroom-a-video | bedroom-W3 | 3.180 | 3.314 [3.023, 3.605] | +13.4 | yes |
| bedroom-a-video | bedroom-W4 | 3.728 | 3.824 [3.476, 4.172] | +9.6 | yes |

## Ceiling heights

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom | 2.640 | 2.607 [2.542, 2.672] | -3.3 | yes |
| bedroom-b | bedroom | 2.640 | 2.604 [2.539, 2.669] | -3.6 | yes |
| bedroom-c | bedroom | 2.640 | 2.613 [2.548, 2.679] | -2.6 | yes |
| bedroom-a-video | bedroom | 2.640 | 2.826 [2.591, 3.062] | +18.7 | yes |

## Opening widths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom-WIN1 | 1.326 | 0.831 [0.803, 0.858] | -49.5 | NO |
| bedroom-a-video | bedroom-WIN1 | 1.326 | 1.492 [1.360, 1.624] | +16.6 | NO |

## Floor areas

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom | 11.859 | 11.155 [10.561, 11.749] | -0.704 | NO |
| bedroom-b | bedroom | 11.859 | 11.014 [10.417, 11.610] | -0.845 | NO |
| bedroom-c | bedroom | 11.859 | 12.237 [11.414, 13.060] | +0.378 | yes |
| bedroom-a-video | bedroom | 11.859 | 12.671 [10.487, 14.856] | +0.812 | yes |

## Opening detection

| Capture | Opening | Outcome | Measured kind | Found kind | Width error (cm) |
|---|---|---|---|---|---|
| bedroom-a | bedroom-D1 | missed | door |  |  |
| bedroom-a | bedroom-WIN1 | matched | window | door | -49.5 |
| bedroom-b | bedroom-D1 | missed | door |  |  |
| bedroom-b | bedroom-WIN1 | missed | window |  |  |
| bedroom-b | room_1-P1 | phantom |  | passage |  |
| bedroom-b | room_1-D1 | phantom |  | door |  |
| bedroom-c | bedroom-D1 | missed | door |  |  |
| bedroom-c | bedroom-WIN1 | missed | window |  |  |
| bedroom-c | room_1-P1 | phantom |  | passage |  |
| bedroom-c | room_1-WIN1 | phantom |  | window |  |
| bedroom-c | room_1-D1 | phantom |  | door |  |
| bedroom-a-video | bedroom-D1 | missed | door |  |  |
| bedroom-a-video | bedroom-WIN1 | matched | window | window | +16.6 |

## Timing (seconds)

| Capture | cloud | damage | drift | fragments | keyframes | layout | levels | measure | openings | planes | poses_and_depth | refine | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bedroom-a | 0.1 | 0.2 | 2.7 | 6.7 | 0.0 | 0.3 | 0.1 | 0.0 | 1.9 | 1.0 | 0.0 | 0.0 | 13.0 |
| bedroom-b | 0.1 | 0.2 | 1.7 | 3.0 | 0.0 | 0.1 | 0.0 | 0.0 | 1.0 | 0.7 | 0.0 | 0.0 | 6.8 |
| bedroom-c | 0.1 | 0.2 | 2.6 | 4.4 | 0.0 | 0.3 | 0.1 | 0.0 | 1.8 | 1.2 | 0.0 | 0.0 | 10.6 |
| bedroom-a-video | 0.1 | 0.5 | 0.8 | 4.3 | 0.0 | 0.1 | 0.0 | 0.0 | 1.9 | 0.4 | 31.8 | 0.0 | 40.0 |
