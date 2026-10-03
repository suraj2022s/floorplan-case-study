# Capture protocol

> Version 2, 2026-10-03. Built from what failed on real captures (see the notes at the end).
> Not yet walked through on an iPhone 15: that is the first thing the benchmark session does.

One page. Follow it in order. No technical knowledge is needed.

## 1. Pick the tier

| Tier | Phone | App | Time |
|---|---|---|---|
| LiDAR | iPhone 15 Pro, 15 Pro Max, or any newer **Pro** model | **Stray Scanner** (free on the App Store, by Kenneth Blomqvist; iOS 18.6 or later) | about 1 minute per room |
| Video | any iPhone 15 or newer | the built-in **Camera** | about 1 minute per room |
| Photos | any iPhone 15 or newer | the built-in **Camera** | about 1 minute per room |

## 2. Prepare the property (every tier)

1. Open every interior door fully. Switch on all the lights.
2. Open curtains and blinds as far as they go.
3. Wipe the camera lenses. No people or pets in view; nothing moves during the capture.

## 3a. LiDAR or video: one continuous recording of the whole property

**LiDAR:** open Stray Scanner, tap the record button. **Video:** open Camera, **Video**, lens
**0.5x** (or **1x** if your phone has no 0.5x), normal video (not Cinematic, Slo-mo or Action).

Hold the phone in front of you at chest height, screen facing you. Walk **slowly**: half your
normal pace. Then:

1. Start **in the middle of the first room**, facing a wall. Start recording.
2. In every room: walk once around the room about 1 m from the walls, keeping the wall you
   pass in view, then stand in the middle and turn once slowly with the phone tilted **up**
   (the line where walls meet the ceiling in view), once with it tilted **down** (where
   walls meet the floor). About 20 seconds per turn.
3. At every doorway: stop 1.5 m before it, show the whole door frame for 2 seconds, walk
   through slowly, turn round and show it again from the other side.
4. At every window: face it from 1.5 m for 2 seconds, frame and sill in view.
5. When every room is done, walk back to the first room's middle and stop recording.

Avoid: fast turns, walking backwards, filming a bare wall from closer than 1 m, pointing at
a mirror, a finger over a camera, stopping and restarting.

## 3b. Photos: one folder per room, 2 to 8 photos in each

Camera, **Photo**, lens **0.5x** (or **1x**), flash off, not Portrait mode, phone sideways
(landscape) and level.

1. **One photo per wall.** Stand with your back against the **middle of a wall** and
   photograph the **opposite wall**. The picture must show the line where that wall meets the
   floor and the line where it meets the ceiling; with 1x, step sideways rather than tilt.
   Go round the room **clockwise**: four photos for a rectangular room, one per wall for an
   L-shaped room.
2. **Corridors:** one photo from each end, looking along it.
3. **Damage (within the 8):** from 1.5 m, straight on, with a corner or the floor line also
   in the picture.

## 4. Hand the files over

Make one folder on the computer for the capture, named after the property.

- **LiDAR:** in Stray Scanner, open the recording and share it (AirDrop, or Save to Files on
  a USB-C drive). Put the folder (or the .zip) in the capture folder as it is.
- **Video:** AirDrop the clip, or copy it by cable after setting **Settings → Photos →
  Transfer to Mac or PC → Keep Originals**.
- **Photos:** one sub-folder per room (`kitchen`, `bedroom1`, ...), originals, unedited.
  Live Photo clips and .AAE files can stay; they are ignored.

Then run one command:

```
uv run floorplan run <the capture folder, .zip or clip>
```

Results appear in `out/<capture name>/`: `plan.png` (the drawing), `plan.json` (every
measurement with its 90% interval) and `run_log.json`. **Read the warnings it prints before
you leave**: if it says a room could not be measured, retake that room while you are there.

---

Why the rules, from real captures (`docs/JOURNAL.md`): a scan started in the hall glued the hall
to the bedroom; fast walking past bare walls broke the video's camera track into pieces;
close-up photos taken anywhere but against a wall cannot be turned into a room.
