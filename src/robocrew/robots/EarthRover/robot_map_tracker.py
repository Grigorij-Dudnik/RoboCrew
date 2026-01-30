import folium
from flask import Flask, request
import threading


app = Flask(__name__)
TRAIL_COORDINATES = []
DATA_LOCK = threading.Lock()

@app.route("/")
def fullscreen():
    """Simple example of a fullscreen map."""
    if not TRAIL_COORDINATES:
        return "No location data yet."
    
    m = folium.Map(location=TRAIL_COORDINATES[-1], zoom_start=24)
    folium.PolyLine(TRAIL_COORDINATES).add_to(m)
    folium.Marker(TRAIL_COORDINATES[-1]).add_to(m)

    html = m.get_root().render()
    return html.replace('<head>', '<head><meta http-equiv="refresh" content="6">')  # adding autorefresh


@app.route("/update_location", methods=['POST'])
def update_location():
    """API endpoint to receive coordinates from the robot."""
    data = request.json
    lat = data.get('lat')
    lon = data.get('lon')
    

    with DATA_LOCK:
        TRAIL_COORDINATES.append((lat, lon))
    print(f"Updated location: {lat}, {lon}")
    return "ok", 200

if __name__ == "__main__":
    app.run(debug=True)