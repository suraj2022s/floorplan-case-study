# Real Stray Scanner recording, four-frame excerpt

These files are an unmodified excerpt of one recording made with the Stray Scanner app on a
LiDAR iPhone. They are here so that the capture reader is tested against what the app really
writes, not only against files this repository wrote itself.

- Source: Diffraction, *Egocentric Kitchen Capture Sample* (2026),
  https://huggingface.co/datasets/diffracting/egocentric-kitchen-sample
- Revision: `75ccd3fc9fbb78be56029539ab1ebf9fb1f3e2f4`
- Recording: `sensors/pepper-dicing.zip`
  (SHA-256 `477b42ac2c8044dc3ecec64a9f86429cc379f3e6ab7ba1a0c7ad24f48db45fa5`)
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0),
  https://creativecommons.org/licenses/by/4.0/

What was taken: `camera_matrix.csv` whole; the header of `odometry.csv` and its rows for
frames 0, 1031, 1758 and 2062; the depth and confidence images of those four frames. Every
byte kept is as the app wrote it. The video (`rgb.mp4`), `imu.csv` and all other frames were
left out to keep the repository small. `python scripts/fetch_samples.py stray-kitchen`
downloads the whole recording.

The scene is a kitchen worktop seen from about 25 cm, not a room. It is used to check the
file format and the camera-pose convention, not to measure anything.
