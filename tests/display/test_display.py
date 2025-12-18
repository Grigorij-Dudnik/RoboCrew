import pytest
from flask import Flask
from robocrew.display import display_bp, set_state_provider

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(display_bp, url_prefix='/robocrew-ui')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_display_page_loads(client):
    response = client.get('/robocrew-ui/display')
    assert response.status_code == 200
    assert b"ARCS Display" in response.data
    # Check if static css link is generated
    assert b"css/display.css" in response.data

def test_display_state_default(client):
    response = client.get('/robocrew-ui/display/state')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['ai_status'] == "Idle"
    assert json_data['blockage']['forward'] is False

def test_display_state_override(client):
    # Override the state provider
    def custom_state():
        return {"ai_status": "Thinking", "custom": True}
    
    set_state_provider(custom_state)
    
    response = client.get('/robocrew-ui/display/state')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['ai_status'] == "Thinking"
    assert json_data['custom'] is True
