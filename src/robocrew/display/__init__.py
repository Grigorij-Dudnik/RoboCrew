try:
    from flask import Blueprint, render_template, jsonify, current_app
except ImportError:
    raise ImportError("The 'robocrew.display' module requires Flask. Please install it using: pip install 'robocrew[gui]'")

import pkg_resources
import os

# Create a Blueprint that knows where to look for templates and static files within the package
display_bp = Blueprint(
    'robocrew_display', 
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/robocrew'
)

# Global state provider - user should override this
_state_provider = lambda: {
    "ai_enabled": False,
    "ai_status": "Idle",
    "control_mode": "idle",
    "precision_mode": False,
    "blockage": {"forward": False, "left": False, "right": False},
    "controller_connected": False,
    "camera_connected": False,
    "arm_connected": False
}

def set_state_provider(provider_func):
    """
    Register a function that returns a dictionary with the robot state.
    Expected keys: ai_enabled, ai_status, control_mode, precision_mode, blockage, etc.
    """
    global _state_provider
    _state_provider = provider_func

@display_bp.route('/display')
def show_display():
    return render_template('display.html')

@display_bp.route('/display/state')
def get_display_state():
    try:
        data = _state_provider()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
