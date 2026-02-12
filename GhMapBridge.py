import json
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class MapBridge(QObject):
    """Bridge between Python and JavaScript for map communication via QWebChannel."""

    # Python → JS signals
    move_to_location = pyqtSignal(str)
    change_map_type = pyqtSignal(str)
    add_site_marker = pyqtSignal(str)
    remove_site_marker = pyqtSignal(str)
    clear_site_markers = pyqtSignal()
    set_click_marker = pyqtSignal(str)
    clear_click_marker = pyqtSignal()

    # Internal signals for Python-side consumers
    map_ready = pyqtSignal()
    map_clicked = pyqtSignal(float, float)
    map_right_clicked = pyqtSignal(float, float)
    zoom_changed = pyqtSignal(int)
    marker_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def on_map_clicked(self, json_str):
        """Called from JS when map is clicked."""
        data = json.loads(json_str)
        self.map_clicked.emit(data["lat"], data["lng"])

    @pyqtSlot(str)
    def on_map_right_clicked(self, json_str):
        """Called from JS when map is right-clicked."""
        data = json.loads(json_str)
        self.map_right_clicked.emit(data["lat"], data["lng"])

    @pyqtSlot()
    def on_map_ready(self):
        """Called from JS when map is fully loaded."""
        self.map_ready.emit()

    @pyqtSlot(int)
    def on_zoom_changed(self, zoom):
        """Called from JS when zoom level changes."""
        self.zoom_changed.emit(zoom)

    @pyqtSlot(str)
    def on_marker_clicked(self, json_str):
        """Called from JS when a site marker is clicked."""
        data = json.loads(json_str)
        self.marker_clicked.emit(data["id"])

    def goto(self, lat, lng, zoom=None):
        """Move map to a location."""
        data = {"lat": lat, "lng": lng}
        if zoom is not None:
            data["zoom"] = zoom
        self.move_to_location.emit(json.dumps(data))

    def set_map_type(self, map_type):
        """Change the map type (ROADMAP, SKYVIEW, HYBRID)."""
        self.change_map_type.emit(map_type)

    def add_marker(self, site_id, lat, lng, name=""):
        """Add a site marker to the map."""
        data = {"id": site_id, "lat": lat, "lng": lng, "name": name}
        self.add_site_marker.emit(json.dumps(data))

    def remove_marker(self, site_id):
        """Remove a site marker from the map."""
        self.remove_site_marker.emit(str(site_id))

    def clear_markers(self):
        """Remove all site markers."""
        self.clear_site_markers.emit()

    def show_click_marker(self, lat, lng):
        """Show a temporary marker at clicked position."""
        self.set_click_marker.emit(json.dumps({"lat": lat, "lng": lng}))

    def hide_click_marker(self):
        """Hide the temporary click marker."""
        self.clear_click_marker.emit()
