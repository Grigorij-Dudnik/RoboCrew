---
name: flat-inspection
description: Inspect flat walls with a Tello drone, find renovation artifacts, and save close centered artifact photos.
---

## Flat Inspection Skill
Use these rules whenever the task is to inspect a flat, wall, room, renovation area, or wall artifact.
This skill is for the controller that performs the inspection. When working under a planner, finish_task means the current subtask is done.

## Inspection Goal
- Inspect every visible wall surface in the flat, not just the center of each room.
- Look for small renovation artifacts: holes, marks, paint gaps, scratches, stains, missing finish, tape residue, dents, or cracks.
- Small artifacts matter, so inspect close enough for wall detail visibility.

## Wall Distance
- Face the wall frontally before a pass; use small turns only to correct skew.
- Keep about 100-200 cm from the front wall during inspection.
- If the wall is small or across the room, move_forward until wall details are visible.
- If the view is mostly plain wall with little floor/ceiling/edge context, move_backward until you at least 100 cm from the wall.

## Wall Pass Behavior
- Scan along a wall with short strafe_left or strafe_right segments while keeping the wall front-facing.
- If no obstacle or target is visible, a recommended strafe length is 50 cm.
- A doorway or opening in front is not the end of the wall pass; record it and continue strafing along the wall until a corner, adjacent wall, or obstacle stops the side scan.
- Do not spin in place to inspect a room. Rotation-only loops are invalid behavior.
- Do not execute more than two consecutive turns without a translation move between them.
- Use turn_left or turn_right when switching to another wall, corner, doorway, or room section.
- Track which wall sections and height runs are already covered in your completion report.

## Height Coverage
- The flat height is about 220 cm.
- Inspect each wall in broad low and high height passes.
- Use these target bands (measured flight height):
  - Low pass: 60-100 cm
  - High pass: 140-180 cm
- Do not mark a wall complete until low and high areas have all been inspected or you report why a height could not be inspected.

## Artifact Photos
- When you see a possible artifact, approach only as much as needed for a useful close image.
- Center the artifact in the camera view before calling save_artifact_photo.
- Save a separate photo for each distinct artifact.
- Include the approximate wall, height run, and description for every saved artifact in the finish_task report.
