# 0001 — Starting decisions

Date: 2026-10-02. Status: accepted, open to revision when measurements say otherwise.

## Capture route: Route 2 (stock apps + one-page protocol)

Route 1 needs a Mac with Xcode and an Apple developer account. The development machine is
Windows, and 45 hours remain. Route 2 uses the built-in Camera app for the photo and video
tiers and a LiDAR logging app for the LiDAR tier. The logging app must give raw depth, poses
and intrinsics, not a finished room model. First candidate: Stray Scanner. It has to be
tested on a current iPhone before the protocol is written around it.

## One shared geometry back-end, three thin front-ends

Each tier's front-end turns its raw files into the same intermediate form: frames with an
image, intrinsics, a camera-to-world pose in a metric gravity-aligned frame, a metric depth
map and a depth uncertainty. Everything after that (planes, layout, openings, stitching,
intervals, output) is one code path that does not know the tier. Intervals widen at the
thinner tiers because the front-end reports larger uncertainties, not because of tier-specific
rules downstream.

## The LiDAR tier runs with no learned model

Plane fitting, layout and opening detection at the LiDAR tier use depth and poses only.
Image-based masks may be added as a second opinion, but the tier must produce a plan without
them. Reasons: it runs cold in minutes on any machine with no weights to download, it is
deterministic, and every step can be explained without a model in the loop.

## Learned models are sized for 4 GB of VRAM

The laptop GPU has 4 GB. Models are loaded one at a time, each is measured on this card
before it is adopted, and each has a CPU fallback. Any model that does not fit is replaced by
a lighter one rather than made a requirement.

## Portable Python, `uv` as the only setup tool

The code is plain Python with no shell-specific steps, so it runs on Windows, Linux and
macOS. The evaluators' machine is unknown and may have no NVIDIA GPU, so Docker with CUDA is
not the only supported path. Setup is `uv sync`; the entry point is a Python command.
Development happens on Windows; WSL2 Ubuntu is used as the clean-machine check.

## Frame conventions are verified on real data

World frame: metres, z-up, gravity-aligned. Conversions from the capture app's convention
happen once, at ingest. A synthetic test cannot prove that our reading of a third-party file
format is right, because the synthetic writer would share the same assumption. The ingest is
therefore checked on a real capture before any accuracy number is trusted.
