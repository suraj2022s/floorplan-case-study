# Capture protocol

> Status: draft. Written 2026-10-02 from the apps' documentation; not yet tested on a phone.

One page. Follow it in order. No technical knowledge is needed.

## 1. Pick the tier

| Tier | Phone | App | Time on site |
|---|---|---|---|
| LiDAR | iPhone 15 Pro or newer Pro model | **Stray Scanner** (free, App Store, by Kenneth Blomqvist; needs iOS 18.6 or later) | about 1 minute per room |
| Video | any iPhone 15 or newer | built-in **Camera** | about 1 minute per room |
| Photos | any iPhone 15 or newer | built-in **Camera** | about 1 minute per room |

## 2. Prepare the property (all tiers)

1. Open every interior door fully and leave it open.
2. Switch on all the lights. Open curtains and blinds so the windows are visible.
3. Wipe the camera lenses.
4. Nothing moves during the capture: no people or pets in view, no doors or furniture moved.

## 3a. LiDAR or video: one continuous recording of the whole property

**LiDAR:** open Stray Scanner and start a new recording.
**Video:** open Camera, choose **Video**, lens **1x**. Not Cinematic, not Slo-mo, not Action mode.

Hold the phone upright (portrait) at chest height with both hands. Then:

1. Start just inside the entrance, facing into the property. Start recording.
2. **In every room**, walk to the middle and do two slow full turns on the spot:
   - first turn with the phone tilted **up**, so the line where the walls meet the ceiling
     stays in view;
   - second turn with the phone tilted **down**, so the line where the walls meet the floor
     stays in view.
   Each turn takes about 20 seconds (30 seconds for video). Slow is better than fast.
3. **At every doorway**, stop 1.5 m in front of it. Point at the left side of the frame, the
   top of the frame and the wall above it, then the right side: 2 seconds each. Walk through
   slowly. Turn around and do the same from the other side.
4. **At every window**, face it from 1.5 m and hold for 2 seconds.
5. In a large room or a room with big furniture, repeat step 2 from a second spot.
6. When every room is done, walk back to where you started, face the way you first faced,
   and stop recording.

Avoid: fast turns; walking backwards; pointing at a mirror or a window from closer than 1 m;
covering the cameras with a finger; stopping and restarting the recording.

## 3b. Photos: one folder per room, 2 to 8 photos in each

Open Camera, choose **Photo**, lens **1x**, flash off. Not Portrait mode.

1. **Corner shots (up to 4).** Stand with your back in a corner. Hold the phone sideways
   (landscape) and level, at chest height. Aim at the opposite corner so that some floor and
   some ceiling are both in the picture. Take one photo. Repeat from each corner you can
   reach. Two opposite corners is the minimum.
2. **Doorway shots (1 per door).** Stand inside the room, 1.5 to 2 m from the open door,
   facing it straight on. The whole door frame and some of the next room must be in the
   picture.
3. **Damage shots (as needed, within the 8).** One photo from about 1.5 m, straight on, with
   the damage in the middle and the nearest corner or the floor line also in the picture.

## 4. Hand the files over

Make one folder per capture on the computer, named after the property.

- **LiDAR:** on the phone open **Files → Browse → On My iPhone → Stray Scanner**. Each
  recording is a folder. Copy the newest folder to a USB-C drive plugged into the phone, or
  share it to a cloud drive. Put that folder on the computer as it is.
- **Video:** copy the clip (`.MOV`) into the capture folder. If you transfer by cable, first
  set **Settings → Photos → Transfer to Mac or PC → Keep Originals**.
- **Photos:** inside the capture folder make one folder per room (`kitchen`, `bedroom1`, …)
  and put that room's photos in it, originals, unedited.

Then run one command:

```
uv run floorplan run <path to the capture folder>
```

The results appear in `out/<capture name>/`: `plan.png` (the drawing), `plan.json` (every
measurement with its 90% interval) and `run_log.json` (timings).
