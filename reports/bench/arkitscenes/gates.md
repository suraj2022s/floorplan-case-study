# Benchmark report: arkitscenes

Public data, used while no iPhone is available: one bedroom from Apple's ARKitScenes dataset, captured three times with the LiDAR of an iPad Pro (ARKit poses and depth) and scanned with a Faro laser. Ground truth is read off the laser scan (bench/ground_truth/arkitscenes-467138.yaml). This is real sensor data with laser ground truth, but it is not the benchmark set the brief specifies: one room only, no multi-room capture, no staged damage, an iPad rather than an iPhone, and captures made by Apple's operators rather than by following our protocol. Fetch with python scripts/fetch_arkitscenes.py.

## Gates

| Tier | Gate | Status | Result | Threshold | Notes |
|---|---|---|---|---|---|
| lidar | Opening widths | **FAIL** | 0/10 = 0% | <= 2 cm on >= 85%; a miss and a phantom each count as a miss | 5 missed, 4 phantom, 1 found but off by more than 2 cm |
| lidar | Ceiling height | **FAIL** | 0/3 rooms within 1.5 cm; worst 3.8 cm | <= 1.5 cm in every room | mean signed error -3.26 cm |
| lidar | Ceiling height, repeat captures | **FAIL** | spread 1.06 cm over 3 room pair(s) | spread across captures <= 1 cm | unrepeatable; mean error -3.26 cm |
| lidar | Repeatability per wall | **not evaluated** | no room captured twice at this tier |  |  |
| lidar | Wall lengths | **not evaluated** | median 12.7 cm, worst 13.9 cm (4.1%); 8 wall(s) not found | set by the Round 1 gate table (not yet in spec/) |  |
| lidar | Whole-property stitch | **not evaluated** | no multi-room capture at this tier |  |  |
| lidar | Interval calibration | **FAIL** | 0/11 = 0% of 90% intervals contain the truth | >= 72% (90% less two standard errors at n=11) | ceiling_height 0/3; floor_area 0/3; opening_width 0/1; wall_length 0/4 |

## Captures

| Capture | Tier | Rooms found / measured | Adjacency | Overlap (m²) | Time (s) |
|---|---|---|---|---|---|
| bedroom-a | lidar | 1 / 1 | correct | 0.000 | 26.2 |
| bedroom-b | lidar | 1 / 1 | correct | 0.000 | 20.4 |
| bedroom-c | lidar | 1 / 1 | correct | 0.000 | 20.5 |

## Wall lengths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom-W1 | 3.188 | 3.056 [3.029, 3.083] | -13.1 | NO |
| bedroom-a | bedroom-W2 | 3.721 | 3.582 [3.551, 3.613] | -13.9 | NO |
| bedroom-a | bedroom-W3 | 3.180 | 3.131 [3.083, 3.179] | -4.9 | NO |
| bedroom-a | bedroom-W4 | 3.728 | 3.605 [3.574, 3.636] | -12.3 | NO |
| bedroom-b | bedroom-W1 | 3.188 | not found | not found |  |
| bedroom-b | bedroom-W2 | 3.721 | not found | not found |  |
| bedroom-b | bedroom-W3 | 3.180 | not found | not found |  |
| bedroom-b | bedroom-W4 | 3.728 | not found | not found |  |
| bedroom-c | bedroom-W1 | 3.188 | not found | not found |  |
| bedroom-c | bedroom-W2 | 3.721 | not found | not found |  |
| bedroom-c | bedroom-W3 | 3.180 | not found | not found |  |
| bedroom-c | bedroom-W4 | 3.728 | not found | not found |  |

## Ceiling heights

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom | 2.640 | 2.607 [2.583, 2.631] | -3.3 | NO |
| bedroom-b | bedroom | 2.640 | 2.602 [2.579, 2.626] | -3.8 | NO |
| bedroom-c | bedroom | 2.640 | 2.613 [2.589, 2.636] | -2.7 | NO |

## Opening widths

| Capture | Item | Truth (m) | Measured [90% interval] | Error (cm) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom-WIN1 | 1.326 | 0.879 [0.828, 0.929] | -44.7 | NO |

## Floor areas

| Capture | Item | Truth (m) | Measured [90% interval] | Error (m²) | Truth in interval |
|---|---|---|---|---|---|
| bedroom-a | bedroom | 11.859 | 11.090 [10.903, 11.277] | -0.769 | NO |
| bedroom-b | bedroom | 11.859 | 12.478 [12.256, 12.700] | +0.619 | NO |
| bedroom-c | bedroom | 11.859 | 15.784 [15.313, 16.255] | +3.925 | NO |

## Opening detection

| Capture | Opening | Outcome | Measured kind | Found kind | Width error (cm) |
|---|---|---|---|---|---|
| bedroom-a | bedroom-D1 | missed | door |  |  |
| bedroom-a | bedroom-WIN1 | matched | window | window | -44.7 |
| bedroom-a | room_1-P1 | phantom |  | passage |  |
| bedroom-b | bedroom-D1 | missed | door |  |  |
| bedroom-b | bedroom-WIN1 | missed | window |  |  |
| bedroom-b | room_1-WIN1 | phantom |  | window |  |
| bedroom-c | bedroom-D1 | missed | door |  |  |
| bedroom-c | bedroom-WIN1 | missed | window |  |  |
| bedroom-c | room_1-P1 | phantom |  | passage |  |
| bedroom-c | room_1-D1 | phantom |  | door |  |

## Timing (seconds)

| Capture | cloud | damage | drift | fragments | keyframes | layout | levels | measure | openings | planes | refine | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bedroom-a | 0.1 | 18.5 | 1.6 | 4.3 | 0.0 | 0.1 | 0.0 | 0.0 | 1.1 | 0.5 | 0.0 | 26.2 |
| bedroom-b | 0.0 | 15.7 | 1.0 | 2.5 | 0.0 | 0.1 | 0.0 | 0.0 | 0.6 | 0.4 | 0.0 | 20.4 |
| bedroom-c | 0.1 | 13.4 | 1.5 | 3.4 | 0.0 | 0.1 | 0.0 | 0.0 | 1.1 | 0.8 | 0.0 | 20.5 |
