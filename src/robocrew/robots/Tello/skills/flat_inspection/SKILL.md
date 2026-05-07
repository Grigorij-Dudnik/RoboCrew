---
name: flat-inspection
description: Inspect flat walls with a Tello drone, find renovation artifacts, and save visible artifact photos.
---

## Flat Inspection Skill
Use these rules whenever the task is to inspect a flat, wall, room, renovation area, or wall artifact.
This skill is for the controller that performs the inspection. When working under a planner, finish_task means the current subtask is done.

## Inspection Goal
- Inspect every visible wall surface in the flat, not just the center of each room.
- Look for small renovation artifacts: holes, marks, paint gaps, scratches, stains, missing finish, tape residue, dents, or cracks.
- Look carefully at the wall itself, including subtle texture changes, small dark or light marks, tape-like rectangles, smudges, uneven paint, exposed patches, chipped corners, and discoloration around sockets, switches, trim, furniture edges, lamps, radiators, windows, and doors.
- Small artifacts matter, so inspect close enough for wall detail visibility.

## Wall Distance
- Before each wall pass, turn until the camera faces the wall straight/perpendicular, not from an angle.
- Keep about 100-200 cm from the front wall during inspection.
- If the wall is small or across the room, move_forward until wall details are visible.
- If the view is mostly plain wall with little floor/ceiling/edge context, move_backward until you at least 100 cm from the wall.

## Wall Pass Behavior
- Scan each wall with a continuous side pass: choose strafe_left or strafe_right and keep using that same direction until you reach the wall edge, corner, adjacent wall, large obstacle, or unsafe position.
- A plain middle section is not a stop condition. If the wall continues left or right, keep strafing in the chosen direction.
- If no obstacle or target is visible, a recommended strafe length is 50 cm.
- After each strafe, inspect the new wall section and decide whether the same side pass can continue. Do not switch walls or finish while the current wall visibly continues in the scan direction.
- A doorway or opening in front is not the end of the wall pass; record it and continue strafing along the wall until a corner, adjacent wall, or obstacle stops the side scan.
- When one side pass reaches a boundary, reverse direction only if needed to cover missed wall sections or a second height band.
- Do not spin in place to inspect a room. Rotation-only loops are invalid behavior.
- Do not execute more than two consecutive turns without a translation move between them.
- Use turn_left or turn_right when switching to another wall, corner, doorway, or room section.
- Track which wall sections and height runs are already covered in your completion report.

## Height Coverage
- The flat height is about 220 cm.
- Inspect each wall in broad low and high height passes.
- Use move_up or move_down only to change scan height band or avoid an obstacle.
- Use these target bands (measured flight height):
  - Low pass: 60-100 cm
  - High pass: 140-180 cm
- Do not mark a wall complete until low and high areas have all been inspected or you report why a height could not be inspected.

## Artifact Photos
- Treat any visible wall problem or unexplained mark as a possible artifact, even if it is small, subtle, or might be dirt, tape, shadow, or furniture contact.
- When you see a possible artifact, approach only as much as needed for a useful close image.
- Call save_artifact_photo when the problem is visible enough for a useful record, even if it is not centered.
- If the problem is already visible enough for a useful record, call save_artifact_photo immediately instead of continuing the scan.
- Save a separate photo for each distinct artifact.
- Include the approximate wall, height run, and description for every saved artifact in the finish_task report.
