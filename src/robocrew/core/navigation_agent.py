import cv2
import base64
import numpy as np
import logging
import time
import os
from typing import List, Optional, Dict, Any
from collections import deque
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model

load_dotenv()

from robocrew.core.utils import capture_image
from robocrew.core.memory_store import memory_store
from robocrew.core.state import state
from robocrew.core.qr_scanner import QRScanner
from robocrew.core.robot_system import RobotSystem

logger = logging.getLogger(__name__)

class NavigationAgent:
    def __init__(
        self, 
        robot_system: RobotSystem,
        model_name: str, 
        tools: List[Any],
        system_prompt: str = None,
        history_len: int = 10
    ):
        self.robot = robot_system
        self.tools = tools
        self.tool_map = {t.name: t for t in tools}
        self.history_len = history_len
        
        if "/" in model_name:
            provider, model = model_name.split("/", 1)
            self.llm = init_chat_model(model, model_provider=provider).bind_tools(tools)
        else:
            self.llm = init_chat_model(model_name).bind_tools(tools)
        
        base_prompt = """You are an intelligent mobile robot navigating a real physical environment.

CRITICAL: USE YOUR OWN VISUAL JUDGMENT
- YOU must look at the actual image and decide if the path is safe.
- If you see ANY wall or obstacle in front of you, DO NOT MOVE FORWARD.

ROBOT CHARACTERISTICS:
- You are approximately 30cm wide.
- Your camera shows what is directly ahead - walls on the sides WILL hit you if you move forward.
- The wheels drift slightly. After turns, you may not be perfectly aligned.

DOORWAYS AND TIGHT OPENINGS:
- ALWAYS enable `precision_mode` BEFORE approaching any door or narrow gap.
- NEVER attempt to drive through a door without Precision Mode enabled.
- Only go through openings that are clearly at least 2x your width.

PRECISION MODE PROTOCOL:
- Use `enable_precision_mode` when approaching a narrow gap.
- SECURITY NOTICE: In precision mode, obstacle avoidance is minimized. Proceed with extreme caution. You rely SOLELY on the guidance lines.
- Once enabled, FOLLOW THE VISUAL GUIDANCE STRICTLY, WITH ONE EXCEPTION:
    - **CLOSE RANGE WARNING**: If you are very close to the door (guidance says "UNSAFE DISTANCE" or you see the door frame filling the view), the Left/Right alignment indicators key become UNRELIABLE. In this specific case, you may ignore the direction if it contradicts your visual judgment, BUT the safest action is usually to **BACK UP** to regain a reliable view.
    - **BLIND COMMIT**: If guidance says "BLIND COMMIT. GO FORWARD.", it means you are crossing the threshold and sensors are masked. MOVE FORWARD CONFIDENTLY.
    - **GUIDANCE IS A HINT**: The line helps you align, but it can be wrong (jitter/jump). If the line points into a wall, IGNORE IT and rely on your own judgment of the door frame.
    - **ROTATION HINTS**: When blocked near a door, guidance may include [ROTATE LEFT/RIGHT to align]. Make a SMALL turn (5-10 degrees) in that direction, then try forward again. Do NOT back up unless you've tried rotating first.
    - **Backing Up**: If you are STUCK at a door, prefer rotating in place to find the gap. Only back up if rotation fails or you are physically wedged.
    - Otherwise, if guide says "ACTION: STOP", OBEY IT.
    - ONLY move forward when guidance says "PERFECT" or if you are confident you are passing through.
- **EXIT PROTOCOL**: DO NOT disable Precision Mode until you have COMPLETELY PASSED the doorframe.
    - If you can still see the door frame or walls on your side, KEEP IT ENABLED.
    - Only disable when the space opens up significantly.

QR CODE CONTEXT:
- You may occasionally see QR codes in the environment. These contain context about the location or objects (e.g., "Room: Kitchen", "Object: Generator").
- **DO NOT EXPECT THEM everywhere**. They are sparse.
- If the system explicitly tells you a QR code was detected ("CONTEXT: Visible QR Code says..."), use that information to orient yourself or confirm you are in the right place.
- Do not ask for QR codes or refuse to move because you don't see one. Rely on your vision and obstacles first.

NAVIGATION RULES:
1. LOOK AT THE IMAGE before every move. What do you actually see?
2. If there is a wall in the view, TURN AWAY first.
3. Start with small moves (0.3m). If clear, you can go further (up to 1.0m).
4. The safety system will STOP you if you miss an obstacle. Trust it.
5. Prefer open spaces. Avoid narrow passages.

WHEN YOU SEE A WALL:
- STOP immediately
- Back up 0.2m
- Turn 45-90 degrees AWAY
- Check again before moving

BACKWARD MOVEMENT SAFETY:
- You have NO rear camera. Going backward is BLIND.
- Only go backward to unstick yourself from a wall.
- NEVER go backward twice in a row. It is unsafe.
- If you back up, your next move MUST be a turn or forward.

MEMORY CONTEXT:
- A compressed memory of your recent actions is provided (e.g., "FWD✓, TL✓, FWD✗").
- ✓ means successful, ✗ means blocked.
- If you see a pattern warning, it means you are repeating the same actions. STOP doing that immediately.
- Use the location history (from QR codes) to understand where you've been.

PERSISTENT NOTES:
- Use `save_note` to remember important observations about the environment (room layouts, landmarks, dead-ends).
- Categories: 'layout', 'landmark', 'obstacle', 'path', 'other'
- Your saved notes persist across sessions and will be shown to you as PERSISTENT MEMORY.
- Example: save_note("layout", "Living room has couch on left, TV on right")
"""
        self.system_prompt = system_prompt or base_prompt
        self.message_history = [SystemMessage(content=self.system_prompt)]
        
        self.current_task = "Idle"
        self.last_image = None
        self.stuck_counter = 0
        self.last_action = None
        self.latest_rotation_hint = None
        
        self.action_history = deque(maxlen=15)
        self.location_history = deque(maxlen=10)
        self.pattern_warning_level = 0
        
        self.qr_scanner = QRScanner()
        self.qr_context = []

    def set_task(self, task: str):
        self.current_task = task
        self.message_history.append(HumanMessage(content=f"New Task: {task}"))
        logger.info(f"Agent task set: {task}")

    def _check_safety(self, image: np.ndarray) -> tuple[list, np.ndarray]:
        if image is None:
            return [], image
            
        try:
            from robocrew.core.obstacle_detection import ObstacleDetector
            
            self.detector = state.get_detector()
                
            safe_actions, overlay, metrics = self.detector.process(image)
            guidance = metrics.get('guidance', '')
            return safe_actions, overlay, guidance, metrics
                
        except Exception as e:
            logger.error(f"Obstacle detection failed: {e}")
            return ["FORWARD", "LEFT", "RIGHT", "BACKWARD"], image, "", {}

    def reset(self):
        self.message_history = [SystemMessage(content=self.system_prompt)]
        self.stuck_counter = 0
        self.last_action = None
        self.current_task = "Idle"
        self.action_history.clear()
        self.location_history.clear()
        self.pattern_warning_level = 0
        logger.info("Agent reset.")

    def _record_action(self, action_name: str, was_blocked: bool = False):
        self.action_history.append({
            'action': action_name,
            'time': time.time(),
            'blocked': was_blocked,
            'pose': state.pose.copy() if state.pose else None
        })

    def _detect_repeating_pattern(self) -> Optional[str]:
        if len(self.action_history) < 4:
            return None
        
        actions = [h['action'] for h in self.action_history]
        
        for pattern_len in [2, 3, 4]:
            if len(actions) < pattern_len * 2:
                continue
            
            pattern = actions[-pattern_len:]
            prev_pattern = actions[-(pattern_len * 2):-pattern_len]
            
            if pattern == prev_pattern:
                if len(actions) >= pattern_len * 3:
                    prev_prev = actions[-(pattern_len * 3):-(pattern_len * 2)]
                    if prev_prev == pattern:
                        return f"SEVERE: [{' → '.join(pattern)}] repeated 3x"
                return f"[{' → '.join(pattern)}] repeated"
        
        blocked_count = sum(1 for h in list(self.action_history)[-6:] if h.get('blocked'))
        if blocked_count >= 4:
            return f"{blocked_count} blocked attempts in last 6 actions"
        
        return None

    def _generate_memory_context(self) -> str:
        lines = []
        
        if self.action_history:
            recent = list(self.action_history)[-8:]
            action_strs = []
            for h in recent:
                name = h['action'].replace('move_', '').replace('turn_', 'T').upper()[:3]
                suffix = '✗' if h.get('blocked') else '✓'
                action_strs.append(f"{name}{suffix}")
            lines.append(f"MEMORY: Recent actions: {', '.join(action_strs)}")
        
        if self.location_history:
            locs = list(self.location_history)[-3:]
            loc_strs = [f"{l['name']}" for l in locs]
            lines.append(f"MEMORY: Locations: {' → '.join(loc_strs)}")
        
        blocked_recent = sum(1 for h in list(self.action_history)[-5:] if h.get('blocked'))
        if blocked_recent >= 2:
            lines.append(f"MEMORY: Streak: {blocked_recent} blocked in last 5 attempts")
        
        pattern = self._detect_repeating_pattern()
        if pattern:
            if "SEVERE" in pattern:
                lines.append(f"⚠️ LOOP DETECTED: {pattern}. MUST try completely different approach!")
            else:
                lines.append(f"⚠️ Pattern: {pattern}. Consider a different strategy.")
        
        persistent = memory_store.generate_context_summary(max_notes=10)
        if persistent:
            lines.append(persistent)
        
        return '\n'.join(lines)

    def _check_stuck_condition(self) -> Optional[str]:
        pattern = self._detect_repeating_pattern()
        
        if pattern and "SEVERE" in pattern:
            logger.warning(f"Severe loop detected: {pattern}. Forcing intervention.")
            self.pattern_warning_level = 0
            self.action_history.clear()
            return "FORCE_TURN_AROUND"
        
        if self.stuck_counter >= 3:
            logger.warning(f"Stuck counter={self.stuck_counter}. Forcing intervention.")
            self.stuck_counter = 0
            return "FORCE_TURN_AROUND"
        
        if pattern:
            self.pattern_warning_level += 1
            if self.pattern_warning_level >= 2:
                logger.warning(f"Pattern persists: {pattern}. Forcing intervention.")
                self.pattern_warning_level = 0
                return "FORCE_TURN_AROUND"
        else:
            self.pattern_warning_level = max(0, self.pattern_warning_level - 1)
        
        return None

    def step(self) -> str:
        if not self.robot.running:
            return "Robot stopped"
            
        frame = self.robot.get_frame()
        if frame is None:
            return "Camera error"
            
        qr_title, qr_points, qr_new_data = self.qr_scanner.scan(frame, state.pose)
        qr_alert = ""
        
        if qr_new_data:
            loc_str = f"x={state.pose.get('x', 0):.1f}, y={state.pose.get('y', 0):.1f}"
            qr_alert = f"CONTEXT UPDATE: Visual System detected meaningful marker: '{qr_new_data}' at estimated location ({loc_str})."
            title = qr_new_data.split(':', 1)[0].strip()
            self.location_history.append({'name': title, 'time': time.time()})

        safe_actions, overlay, guidance, metrics = self._check_safety(frame)
        self.latest_rotation_hint = metrics.get('rotation_hint')
        
        if overlay is not None and qr_points is not None:
             try:
                 points = qr_points
                 if points.ndim == 3 and points.shape[0] == 1:
                    points = points[0]
                 
                 points = points.astype(int)
                 
                 for i in range(len(points)):
                     pt1 = tuple(points[i])
                     pt2 = tuple(points[(i+1) % len(points)])
                     cv2.line(overlay, pt1, pt2, (0, 255, 0), 3)
                 
                 if qr_title:
                     x, y = points[0]
                     cv2.putText(overlay, qr_title, (int(x), int(y) + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
             except Exception as e:
                 logger.warning(f"Failed to draw QR visuals: {e}")
        
        display_frame = overlay if overlay is not None else frame
        
        forced_action = self._check_stuck_condition()
        
        _, buffer = cv2.imencode('.jpg', display_frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        content = [
            {"type": "text", "text": f"Task: {self.current_task}"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
        ]
        
        reflex_msg = f"REFLEX SYSTEM: Allowed actions are {safe_actions}. Green Marked Paths are SAFE. Red Marked Areas are BLOCKED."
        
        memory_context = self._generate_memory_context()
        if memory_context:
            reflex_msg = memory_context + "\n" + reflex_msg
        
        c_fwd = metrics.get('c_fwd', 0)
        
        if state.precision_mode:
            reflex_msg += f"\nVISUAL GUIDANCE: {guidance}"
            reflex_msg += "\nPRECISION MODE: ON. Use the guidance to align with the gap."
            
            if c_fwd < 250:
                 reflex_msg += "\n(HINT: The path ahead seems OPEN/CLEAR. You should probably DISABLE PRECISION MODE now to move faster.)"
        else:
            reflex_msg += "\nPRECISION MODE: OFF."
            if "FORWARD" not in safe_actions:
                 reflex_msg += " (HINT: If you are trying to pass a narrow door/gap, ENABLE PRECISION MODE to allow closer approach.)"
        
        if c_fwd > 380:
             reflex_msg += "\n(WARNING: You are very close to an obstacle. Visual indicators might be distorted. Back up if unsure.)"
        
        if qr_new_data:
             reflex_msg += f"\nCONTEXT: Visible QR Code says: '{qr_new_data}'. Use this info if relevant."

        if self.stuck_counter > 0:
            reflex_msg += f"\nWARNING: You have been blocked {self.stuck_counter} times recently. You are likely STUCK. Do NOT try the same action again. Turn around or find a new path."
            
        if forced_action == "FORCE_TURN_AROUND":
            reflex_msg += "\nCRITICAL: YOU ARE STUCK. IGNORING YOUR OUTPUT. FORCING A TURN."
            
        content.append({
             "type": "text", 
             "text": reflex_msg
        })
        
        if qr_alert:
            content.append({
                "type": "text", 
                "text": qr_alert
            })
            
        self.message_history.append(HumanMessage(content=content))

        if forced_action == "FORCE_TURN_AROUND":
             logger.info("Executing FORCED TURN AROUND due to stuck condition")
             if "turn_left" in self.tool_map:
                 self.tool_map["turn_left"].invoke({"angle_degrees": 90})
             elif "turn_right" in self.tool_map:
                 self.tool_map["turn_right"].invoke({"angle_degrees": 90})
                 
             self.message_history.append(ToolMessage(content="System forced 90 degree turn to unstuck robot.", tool_call_id="system_forced_turn"))
             return "Stuck Detected - Forced Turn Executed"
        
        try:
            response = self.llm.invoke(self.message_history)
            self.message_history.append(response)
            
            if len(self.message_history) > 5:
                self.message_history = [self.message_history[0]] + self.message_history[-4:]
            
            if response.tool_calls:
                any_blocked = False
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    args = tool_call["args"]
                    logger.info(f"Agent executing: {tool_name}({args})")
                    
                    action_map = {
                        "move_forward": "FORWARD",
                        "turn_left": "LEFT",
                        "turn_right": "RIGHT",
                        "move_backward": "BACKWARD"
                    }
                    
                    blocked = False
                    if tool_name in action_map:
                        required_action = action_map[tool_name]
                        if required_action not in safe_actions:
                            blocked = True
                            result = f"REFLEX SYSTEM INTERVENTION: Action '{tool_name}' BLOCKED. detected obstacle. Allowed: {safe_actions}."
                            
                            if self.latest_rotation_hint:
                                result += f" HINT: {self.latest_rotation_hint}. TRY THIS INSTEAD OF BACKING UP."
                            else:
                                result += " Please choose another path."
                        
                        if tool_name == "move_backward":
                            if self.last_action == "move_backward":
                                blocked = True
                                result = "SAFETY INTERVENTION: You cannot move backward twice in a row. You are blind behind you. Please TURN or move FORWARD."
                    
                    if blocked:
                        any_blocked = True
                        self.stuck_counter += 1
                        self._record_action(tool_name, was_blocked=True)
                        logger.warning(f"Action blocked. Stuck counter: {self.stuck_counter}")
                    
                    if not blocked:
                        if tool_name in self.tool_map:
                            tool = self.tool_map[tool_name]
                            try:
                                result = tool.invoke(args)
                                self.last_action = tool_name
                                self._record_action(tool_name, was_blocked=False)
                                
                                if tool_name in ["move_forward", "turn_left", "turn_right"]:
                                     self.stuck_counter = 0
                                     
                            except Exception as e:
                                result = f"Error executing {tool_name}: {e}"
                        else:
                            result = f"Unknown tool: {tool_name}"
                            logger.error(result)
                            
                    self.message_history.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
                    
                if not any_blocked and len(response.tool_calls) > 0:
                     pass

                return f"Executed {len(response.tool_calls)} actions"
            else:
                return "Thinking..."
                
        except Exception as e:
            logger.error(f"Agent step error: {e}")
            return f"Error: {e}"
