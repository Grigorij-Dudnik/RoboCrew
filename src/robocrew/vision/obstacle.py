import cv2
import numpy as np
import logging
import threading
from collections import deque
from typing import List, Tuple, Optional, Dict, Set

logger = logging.getLogger(__name__)

class ObstacleDetector:
    """
    Vision-based obstacle detection and navigation assistance system.
    
    Features:
    - Vertical edge detection for obstacle identification.
    - Dynamic safety thresholds for different movement modes.
    - "Precision Mode" for aligning with narrow gaps/doors.
    - Continuous safety history to prevent flickering/hysteresis.
    """
    
    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        
        # Detection Thresholds
        # Y-coordinate thresholds (0=top, 480=bottom)
        self.obstacle_threshold_y = 420  # Stop when obstacle is very close
        self.center_x_threshold = 310
        self.min_edge_pixels = 200      # Minimum edge pixels to consider valid visual input
        
        # Hysteresis / Safety History
        self.history_len = 12  # Approx 0.5-1.0s buffer
        self.block_history = deque(maxlen=self.history_len)
        self.lock = threading.Lock()
        
        # Public State
        self.latest_blockage = {
            'forward': False,
            'left': False,
            'right': False
        }
        
        # EMA Smoothing for Precision Mode
        self.last_gap_center = None
        self.last_gap_update_time = 0.0
        self.gap_lock_duration = 5.0  # seconds
        
    def process(self, frame: np.ndarray, precision_mode: bool = False, approach_mode: bool = False) -> Tuple[List[str], Optional[np.ndarray], Dict]:
        """
        Process a video frame to detect obstacles and determine safe navigation actions.
        
        Args:
            frame (np.ndarray): Input video frame (BGR).
            precision_mode (bool): Whether precision alignment logic is active.
            approach_mode (bool): Whether safety thresholds are relaxed for approach.
            
        Returns:
            tuple: (
                safe_actions (list): List of allowed actions ['FORWARD', 'LEFT', 'RIGHT', 'BACKWARD'],
                overlay (np.ndarray): Visualization frame,
                metrics (dict): Internal detection metrics
            )
        """
        if frame is None:
            return ["STOP"], None, {}

        # 1. Image Preprocessing & Edge Detection
        edges, total_edge_pixels = self._detect_edges(frame)
        h, w = edges.shape
        
        # 2. Column Scanning
        edge_points = self._scan_columns(edges, w, h)
        
        # Visualization Setup
        overlay = frame.copy()
        shapes = frame.copy()
        self._draw_scan_points(overlay, edge_points)

        # 3. Analyze Obstacle Distances
        # Divide view into chunks: Left, Center, Right
        # Center is narrower to focus on immediate path.
        center_width = len(edge_points) // 5
        side_width = (len(edge_points) - center_width) // 2
        
        c_left = self._get_chunk_average(edge_points[:side_width])
        c_fwd = self._get_chunk_average(edge_points[side_width : side_width + center_width])
        c_right = self._get_chunk_average(edge_points[side_width + center_width:])

        # 4. Check Safety Constraints
        is_blind = total_edge_pixels < self.min_edge_pixels
        instant_blocked, rotation_hint = self._determine_blocked_directions(
            c_left, c_fwd, c_right, is_blind, precision_mode, approach_mode
        )
        
        # Update Safety History & Public State
        safe_actions = self._update_safety_state(instant_blocked, is_blind, shapes, overlay, w, h)

        # 5. Compute Precision Guidance (if enabled)
        guidance = ""
        if precision_mode:
            guidance = self._compute_precision_guidance(edge_points, c_fwd, w, h, overlay, shapes, precision_mode)

        # Blend Visualization
        alpha = 0.4
        cv2.addWeighted(shapes, alpha, overlay, 1 - alpha, 0, overlay)
        if guidance:
            cv2.putText(overlay, guidance, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Draw Mode Status
        mode_text = "MODE: STANDARD"
        mode_color = (0, 255, 0) # Green
        
        if approach_mode:
            mode_text = "MODE: APPROACH (SAFETY OFF)"
            mode_color = (0, 0, 255) # Red
        elif precision_mode:
            mode_text = "MODE: PRECISION"
            mode_color = (255, 255, 0) # Cyan
            
        cv2.putText(overlay, mode_text, (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)

        return safe_actions, overlay, {
            'c_left': c_left, 
            'c_fwd': c_fwd, 
            'c_right': c_right, 
            'edges': total_edge_pixels,
            'guidance': guidance,
            'rotation_hint': rotation_hint
        }

    def _detect_edges(self, frame):
        """Apply filters and Canny edge detection."""
        filtered = cv2.bilateralFilter(frame, 9, 75, 75)
        edges = cv2.Canny(filtered, 50, 150)
        total_pixels = np.count_nonzero(edges)
        return edges, total_pixels

    def _scan_columns(self, edges, w, h, step=5):
        """Scan columns to find the lowest (closest) edge pixel."""
        edge_points = []
        for x in range(0, w, step):
            detected_y = 0
            # Scan bottom-up
            for y in range(h - 1, -1, -1):
                if edges[y, x] == 255:
                    detected_y = y
                    break
            edge_points.append((x, detected_y))
        return edge_points

    def _draw_scan_points(self, overlay, edge_points):
        """Draw detected obstacles on the overlay."""
        for x, y in edge_points:
            if y > 0:
                cv2.circle(overlay, (x, y), 2, (0, 0, 255), -1)

    def _get_chunk_average(self, chunk, top_n=10):
        """
        Calculate average Y-position of the closest points in a chunk.
        Robust against single-pixel noise.
        """
        if not chunk:
            return 0
        ys = sorted([p[1] for p in chunk], reverse=True)  # Descending (Closest first)
        top_values = ys[:top_n]
        if not top_values:
            return 0
        return sum(top_values) / len(top_values)

    def _determine_blocked_directions(self, c_left, c_fwd, c_right, is_blind, precision_mode, approach_mode):
        """Determine which directions are unsafe based on thresholds."""
        blocked = set()
        rotation_hint = None
        
        threshold = self.obstacle_threshold_y
        if precision_mode:
             threshold += 30
        
        # In Approach Mode, we allow obstacles to come VERY close (bottom of screen)
        if approach_mode:
             threshold = 470 # Almost 480 (bottom)
             
        side_threshold = threshold + 50
        
        if is_blind:
            blocked.add("FORWARD")
        else:
            if precision_mode:
                 if c_fwd > 460:
                     blocked.add("FORWARD")
                     # Provide rotation hint based on clearance
                     if c_left < c_right:
                         rotation_hint = "ROTATE LEFT to align"
                     elif c_right < c_left:
                         rotation_hint = "ROTATE RIGHT to align"
            
            elif approach_mode:
                # APPROACH MODE: DISABLE FORWARD SAFETY
                # We want to touch objects. Only check sides.
                pass 
                
            else:
                 if c_fwd > threshold:
                     blocked.add("FORWARD")
                 if c_left > side_threshold:
                     blocked.add("LEFT")
                 if c_right > side_threshold:
                     blocked.add("RIGHT")
                
        return blocked, rotation_hint

    def _update_safety_state(self, instant_blocked, is_blind, shapes, overlay, w, h):
        """
        Update shared history buffer and determine final safe actions.
        Draws safety indicators on the overlay.
        """
        with self.lock:
            self.block_history.append(instant_blocked)
            
            # Combine history to filter noise
            persistent_blocked = set()
            for b_set in self.block_history:
                persistent_blocked.update(b_set)
            
            # Update public state
            self.latest_blockage = {
                'forward': "FORWARD" in persistent_blocked,
                'left': "LEFT" in persistent_blocked,
                'right': "RIGHT" in persistent_blocked
            }
            
        safe_actions = ["BACKWARD"] # Backward is mostly always safe (blind)
        
        # Visualize Blockages
        cx = w // 2
        cy = h // 2
        
        if is_blind:
            cv2.rectangle(shapes, (int(w*0.2), int(h*0.2)), (int(w*0.8), int(h*0.8)), (0, 0, 255), -1)
            cv2.putText(overlay, "BLOCKED (NO VISUALS)", (int(w*0.3), cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        else:
            if "FORWARD" in persistent_blocked:
                cv2.rectangle(shapes, (int(w*0.33), cy), (int(w*0.66), h), (0, 0, 255), -1)
            else:
                safe_actions.append("FORWARD")
                # Draw Safe Zone
                pts = np.array([[int(w*0.3), h], [int(w*0.7), h], [int(w*0.6), int(h*0.4)], [int(w*0.4), int(h*0.4)]], np.int32)
                cv2.fillPoly(shapes, [pts], (0, 255, 0))
                cv2.putText(overlay, "FWD OK", (int(w*0.45), int(h*0.8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

            if "LEFT" in persistent_blocked:
                cv2.rectangle(shapes, (0, cy), (int(w*0.33), h), (0, 0, 255), -1)
            else:
                safe_actions.append("LEFT")
                
            if "RIGHT" in persistent_blocked:
                cv2.rectangle(shapes, (int(w*0.66), cy), (w, h), (0, 0, 255), -1)
            else:
                safe_actions.append("RIGHT")
                
        return safe_actions

    def _compute_precision_guidance(self, edge_points, c_fwd, w, h, overlay, shapes, precision_mode):
        """
        Identify usable gaps and provide alignment guidance.
        """
        # 1. Smooth Y-values to reduce noise
        raw_ys = [p[1] for p in edge_points]
        smoothed_ys = []
        for i in range(len(raw_ys)):
            prev_y = raw_ys[i-1] if i > 0 else raw_ys[i]
            next_y = raw_ys[i+1] if i < len(raw_ys)-1 else raw_ys[i]
            smoothed_ys.append(sorted([prev_y, raw_ys[i], next_y])[1]) # Median
            
        # 2. Identify "Passable" Columns (Obstacle is far away)
        passable_limit_y = 350
        is_very_close = c_fwd > 420
        
        # CLOSE-RANGE BYPASS: When very close, gap detection is unreliable
        if is_very_close:
            return "BLIND COMMIT: Decide based on what you see."
        
        passable_indices = []
        for i, y in enumerate(smoothed_ys):
             effective_y = y
             if precision_mode and y > 420:
                 effective_y = 0 
                 
             if effective_y < passable_limit_y:
                 passable_indices.append(edge_points[i][0])
        
        if not passable_indices:
            return ""

        # 3. Find Largest Contiguous Gap
        clusters = []
        current_cluster = [passable_indices[0]]
        for i in range(1, len(passable_indices)):
            if passable_indices[i] - passable_indices[i-1] <= 8:
                current_cluster.append(passable_indices[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [passable_indices[i]]
        clusters.append(current_cluster)
        
        # Filter small gaps (noise) and find cluster closest to center
        valid_clusters = [c for c in clusters if (c[-1] - c[0]) > 20]
        
        if not valid_clusters:
            return ""
            
        # Smart Gap Selection
        image_center = w // 2
        
        def gap_score(cluster):
            width = cluster[-1] - cluster[0]
            center = (cluster[0] + cluster[-1]) // 2
            dist = abs(center - image_center)
            return width - (dist * 1.2)
            
        best_cluster = max(valid_clusters, key=gap_score)
        
        raw_gap_center = (best_cluster[0] + best_cluster[-1]) // 2
        
        # Time-based smoothing
        import time
        current_time = time.time()
        
        if self.last_gap_center is None:
            self.last_gap_center = raw_gap_center
            self.last_gap_update_time = current_time
        else:
            time_since_update = current_time - self.last_gap_update_time
            if time_since_update >= self.gap_lock_duration:
                # Lock expired, allow update with EMA
                alpha = 0.5
                self.last_gap_center = int(alpha * raw_gap_center + (1 - alpha) * self.last_gap_center)
                self.last_gap_update_time = current_time
                
        gap_center = self.last_gap_center
        
        # Draw Target Line
        cv2.line(overlay, (gap_center, h//2), (gap_center, h), (255, 255, 0), 2)
        cv2.putText(overlay, "TARGET", (gap_center - 20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        
        # 4. Generate Guidance
        center_offset = gap_center - (w // 2)
        is_aligned = abs(center_offset) < 20
        is_too_close_to_align = c_fwd > 440
        
        if is_aligned:
            cv2.line(overlay, (gap_center, h//2), (gap_center, h), (0, 255, 0), 3)
            return ""
        else:
            if is_too_close_to_align:
                cv2.rectangle(shapes, (0, 0), (w, h), (0, 0, 255), 20)
                return ""
            elif center_offset < 0:
                cv2.line(overlay, (gap_center, h//2), (gap_center, h), (0, 0, 255), 2)
                return ""
            else:
                cv2.line(overlay, (gap_center, h//2), (gap_center, h), (0, 0, 255), 2)
                return ""
