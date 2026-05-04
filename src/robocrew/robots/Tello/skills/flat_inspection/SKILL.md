---
name: flat-inspection
description: Inspect flat walls with a DJI Tello drone, find renovation artifacts, and save close centered artifact photos.
---

## Flat Inspection Skill
Use these rules whenever the task is to inspect a flat, wall, room, renovation area, or wall artifact.
This skill is for the controller that performs the inspection. A planner should delegate areas and desired results, not use this as a movement checklist.
When working under a planner, finish_task means the current subtask is done. Do not land after a subtask unless the planner asks you to land or you are blocked.

## Inspection Goal
- Inspect every visible wall surface in the flat, not just the center of each room.
- Look for small renovation artifacts on walls: holes, marks, paint gaps, scratches, stains, missing finish, tape residue, dents, cracks, or other things that should not be there.
- Small artifacts matter. Move slowly and deliberately enough that the camera can see wall details.

## Wall Distance
- For inspection passes, keep the drone facing the wall being inspected.
- Fly no farther than 100 cm from the wall in front of the drone when practical.
- If the wall is farther away, approach until the wall fills enough of the camera view to inspect small artifacts, while preserving stopping margin.
- Do not intentionally inspect walls from the middle of a room if a closer position is available.
- If the drone is very close to the wall, stop approaching and use sideways movement or turning to continue coverage.

## Height Coverage
- The flat height is about 220 cm.
- Inspect each wall in broad low, middle, and high height passes.
- Use the measured height to choose the next broad pass; do not fine-tune height with moves under 20 cm.
- If the current height is already close enough for the intended pass, continue the wall pass.
- Do not mark a wall complete until low, middle, and high areas have all been inspected or you report why a height could not be inspected.

## Wall Pass Behavior
- Move along the wall in short, controlled segments while keeping the wall in front of the camera.
- Use strafe_left or strafe_right to scan along a wall while maintaining the same viewing angle.
- If a strafe tool response says the movement failed, assume there is a wall or obstacle on that side.
- Do not repeat a failed strafe blindly. Turn toward that side, inspect what blocked the movement, adjust position, then return to the wall inspection run.
- Use turn_left or turn_right when switching to another wall, corner, doorway, or room section.
- Pause after each movement to reassess the camera view before choosing the next action.
- Track which wall sections and height runs are already covered in your completion report.

## Artifact Photos
- When you see a possible artifact, approach only as much as needed for a useful close image.
- Center the artifact in the camera view before calling save_artifact_photo.
- Save a separate photo for each distinct artifact.
- Include the approximate wall, height run, and description for every saved artifact in the finish_task report.
