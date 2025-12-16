from robocrew.config import (
    ARM_XY_SENSITIVITY, ARM_WRIST_SENSITIVITY,
    ARM_SHOULDER_PAN_STEP, ARM_WRIST_FLEX_STEP
)

class ArmController:
    def __init__(self):
        self.shoulder_pan = 0
        self.shoulder_lift = 0
        self.elbow_flex = 0
        self.wrist_flex = 0
        self.wrist_roll = 0
        self.gripper = 0
        
        self.home_positions = {
            'shoulder_pan': 0,
            'shoulder_lift': -20,
            'elbow_flex': 20,
            'wrist_flex': -40,
            'wrist_roll': 0,
            'gripper': 0
        }

    def reset_to_home(self):
        self.shoulder_pan = self.home_positions['shoulder_pan']
        self.shoulder_lift = self.home_positions['shoulder_lift']
        self.elbow_flex = self.home_positions['elbow_flex']
        self.wrist_flex = self.home_positions['wrist_flex']
        self.wrist_roll = self.home_positions['wrist_roll']
        self.gripper = self.home_positions['gripper']
        return self.get_targets()

    def handle_mouse_move(self, delta_x, delta_y):
        self.shoulder_pan -= delta_x * ARM_XY_SENSITIVITY
        self.shoulder_lift += delta_y * ARM_XY_SENSITIVITY
        
        self.shoulder_pan = max(-90, min(90, self.shoulder_pan))
        self.shoulder_lift = max(-30, min(30, self.shoulder_lift))
        
        return self.get_targets()

    def handle_scroll(self, delta):
        self.wrist_roll += delta * ARM_WRIST_SENSITIVITY
        self.wrist_roll = max(-90, min(90, self.wrist_roll))
        return self.get_targets()

    def handle_shoulder_pan(self, direction):
        self.shoulder_pan += direction * ARM_SHOULDER_PAN_STEP
        self.shoulder_pan = max(-90, min(90, self.shoulder_pan))

    def handle_wrist_flex(self, direction):
        self.wrist_flex += direction * ARM_WRIST_FLEX_STEP
        self.wrist_flex = max(-90, min(90, self.wrist_flex))

    def handle_elbow_flex(self, direction):
        self.elbow_flex += direction * ARM_SHOULDER_PAN_STEP
        self.elbow_flex = max(-90, min(90, self.elbow_flex))

    def set_gripper(self, closed: bool):
        self.gripper = 100 if closed else 0

    def get_targets(self):
        return {
            'shoulder_pan': int(self.shoulder_pan),
            'shoulder_lift': int(self.shoulder_lift),
            'elbow_flex': int(self.elbow_flex),
            'wrist_flex': int(self.wrist_flex),
            'wrist_roll': int(self.wrist_roll),
            'gripper': int(self.gripper)
        }

arm_controller = ArmController()
