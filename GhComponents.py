import os
import json
import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QSlider, QPushButton, QGroupBox, QFormLayout, QTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog, QScrollArea,
    QGridLayout, QSplitter, QFrame, QTabWidget, QLineEdit, QMessageBox,
    QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QThread
from PyQt6.QtGui import QPixmap, QImage, QCursor
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from GhCommons import (
    resource_path, DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_ZOOM,
    MAP_TYPES, get_screenshots_dir, calculate_risk_score, get_risk_level,
    get_photos_dir, fetch_road_distance, road_distance_to_score,
    fetch_wayback_summer_version, fetch_wayback_summer_by_capture,
)
from GhLandCover import analyze_landcover
from GhMapBridge import MapBridge
from GhModels import (
    GeoHeritageSite, SiteScreenshot, RiskEvaluation, SitePhoto, db,
)


class MapWidget(QWidget):
    """Map display widget using QWebEngineView with Leaflet/OSM."""

    map_clicked = pyqtSignal(float, float)
    map_right_clicked = pyqtSignal(float, float)
    add_site_requested = pyqtSignal(float, float)
    zoom_changed = pyqtSignal(int)
    map_ready = pyqtSignal()
    marker_clicked = pyqtSignal(int)
    screenshot_saved = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_zoom = DEFAULT_ZOOM
        self.current_map_type = "ROADMAP"
        self._is_ready = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()

        # Allow local HTML to load remote tile servers
        settings = self.web_view.page().settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

        self.bridge = MapBridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.bridge.map_clicked.connect(self._on_map_clicked)
        self.bridge.map_right_clicked.connect(self._on_map_right_clicked)
        self.bridge.zoom_changed.connect(self._on_zoom_changed)
        self.bridge.map_ready.connect(self._on_map_ready)
        self.bridge.marker_clicked.connect(self.marker_clicked.emit)

        html_path = resource_path(os.path.join("templates", "map_view.html"))
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

        layout.addWidget(self.web_view)

    def _on_map_clicked(self, lat, lng):
        self.map_clicked.emit(lat, lng)

    def _on_map_right_clicked(self, lat, lng):
        self.map_right_clicked.emit(lat, lng)
        menu = QMenu(self)
        add_action = menu.addAction("Add Site Here")
        menu.addSeparator()
        capture_action = menu.addAction("Capture Screenshot")
        action = menu.exec(QCursor.pos())
        if action == add_action:
            self.add_site_requested.emit(lat, lng)
        elif action == capture_action:
            self.screenshot_saved.emit("")  # trigger via main window

    def _on_zoom_changed(self, zoom):
        self.current_zoom = zoom
        self.zoom_changed.emit(zoom)

    def _on_map_ready(self):
        self._is_ready = True
        self.map_ready.emit()

    def goto(self, lat, lng, zoom=None):
        if self._is_ready:
            self.bridge.goto(lat, lng, zoom)

    def set_map_type(self, map_type):
        self.current_map_type = map_type
        if self._is_ready:
            self.bridge.set_map_type(map_type)

    def add_site_marker(self, site_id, lat, lng, name=""):
        if self._is_ready:
            self.bridge.add_marker(site_id, lat, lng, name)

    def remove_site_marker(self, site_id):
        if self._is_ready:
            self.bridge.remove_marker(site_id)

    def clear_site_markers(self):
        if self._is_ready:
            self.bridge.clear_markers()

    def show_road_line(self, site_lat, site_lng, road_lat, road_lng,
                       distance_m=None):
        if self._is_ready:
            self.bridge.draw_road_line(site_lat, site_lng, road_lat, road_lng,
                                       distance_m)

    def clear_road_line(self):
        if self._is_ready:
            self.bridge.remove_road_line()

    def show_analysis_circle(self, lat, lng, radius_m):
        if self._is_ready:
            self.bridge.draw_analysis_circle(lat, lng, radius_m)

    def clear_analysis_circle(self):
        if self._is_ready:
            self.bridge.remove_analysis_circle()

    def highlight_site_marker(self, site_id):
        if self._is_ready:
            self.bridge.highlight_marker(site_id)

    def set_wayback_version(self, release_num, date_str="", metadata_url=""):
        if self._is_ready:
            self.bridge.set_wayback(release_num, date_str, metadata_url)

    def capture_screenshot(self, site):
        """Capture current map view as screenshot."""
        if not site:
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{site.id}_{timestamp}.png"
        filepath = os.path.join(get_screenshots_dir(), filename)

        pixmap = self.web_view.grab()
        pixmap.save(filepath, "PNG")

        record = SiteScreenshot.create(
            site=site,
            file_path=filepath,
            map_type=self.current_map_type,
            zoom_level=self.current_zoom,
        )

        self.screenshot_saved.emit(filepath)
        return record


class SiteListWidget(QWidget):
    """Widget displaying list of geoheritage sites."""

    site_selected = pyqtSignal(object)  # GeoHeritageSite or None

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Sites")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

    def load_sites(self):
        self.list_widget.clear()
        sites = GeoHeritageSite.select().order_by(GeoHeritageSite.site_name)
        for site in sites:
            item = QListWidgetItem(site.site_name)
            item.setData(Qt.ItemDataRole.UserRole, site.id)
            self.list_widget.addItem(item)

    def _on_selection_changed(self, current, previous):
        if current:
            site_id = current.data(Qt.ItemDataRole.UserRole)
            try:
                site = GeoHeritageSite.get_by_id(site_id)
                self.site_selected.emit(site)
            except GeoHeritageSite.DoesNotExist:
                self.site_selected.emit(None)
        else:
            self.site_selected.emit(None)

    def select_site_by_id(self, site_id):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == site_id:
                self.list_widget.setCurrentItem(item)
                return


class SiteInfoPanel(QWidget):
    """Panel for viewing and editing site information in-place."""

    site_updated = pyqtSignal()

    SITE_TYPES = [
        "", "Geological", "Geomorphological", "Paleontological",
        "Mineralogical", "Structural", "Volcanic", "Other",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_site = None
        self._loading = False

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Site name")
        self.name_edit.editingFinished.connect(self._save_field)
        layout.addRow("Name:", self.name_edit)

        coord_layout = QHBoxLayout()
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(6)
        self.lat_spin.editingFinished.connect(self._save_field)
        self.lng_spin = QDoubleSpinBox()
        self.lng_spin.setRange(-180.0, 180.0)
        self.lng_spin.setDecimals(6)
        self.lng_spin.editingFinished.connect(self._save_field)
        coord_layout.addWidget(QLabel("Lat:"))
        coord_layout.addWidget(self.lat_spin)
        coord_layout.addWidget(QLabel("Lng:"))
        coord_layout.addWidget(self.lng_spin)
        layout.addRow("Coordinates:", coord_layout)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Address")
        self.address_edit.editingFinished.connect(self._save_field)
        layout.addRow("Address:", self.address_edit)

        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        self.type_combo.addItems(self.SITE_TYPES)
        self.type_combo.currentTextChanged.connect(self._save_field)
        layout.addRow("Type:", self.type_combo)

        self.desc_text = QTextEdit()
        self.desc_text.setMaximumHeight(100)
        self.desc_text.textChanged.connect(self._save_field)
        layout.addRow("Description:", self.desc_text)

    def set_site(self, site):
        self._loading = True
        self.current_site = site
        if site:
            self.name_edit.setText(site.site_name)
            self.lat_spin.setValue(site.latitude)
            self.lng_spin.setValue(site.longitude)
            self.address_edit.setText(site.address or "")
            self.type_combo.setCurrentText(site.site_type or "")
            self.desc_text.setPlainText(site.site_desc or "")
            self._set_enabled(True)
        else:
            self.name_edit.clear()
            self.lat_spin.setValue(0.0)
            self.lng_spin.setValue(0.0)
            self.address_edit.clear()
            self.type_combo.setCurrentIndex(0)
            self.desc_text.clear()
            self._set_enabled(False)
        self._loading = False

    def _set_enabled(self, enabled):
        self.name_edit.setEnabled(enabled)
        self.lat_spin.setEnabled(enabled)
        self.lng_spin.setEnabled(enabled)
        self.address_edit.setEnabled(enabled)
        self.type_combo.setEnabled(enabled)
        self.desc_text.setEnabled(enabled)

    def _save_field(self):
        if self._loading or not self.current_site:
            return
        self.current_site.site_name = self.name_edit.text()
        self.current_site.latitude = self.lat_spin.value()
        self.current_site.longitude = self.lng_spin.value()
        self.current_site.address = self.address_edit.text() or None
        self.current_site.site_type = self.type_combo.currentText() or None
        self.current_site.site_desc = self.desc_text.toPlainText() or None
        self.current_site.save()
        self.site_updated.emit()


class RoadDistanceWorker(QThread):
    """Background worker for OSRM road distance measurement."""

    finished = pyqtSignal(float, float, float)  # distance_m, snap_lat, snap_lng
    error = pyqtSignal(str)

    def __init__(self, lat, lng, parent=None):
        super().__init__(parent)
        self.lat = lat
        self.lng = lng

    def run(self):
        try:
            distance, snap_lat, snap_lng = fetch_road_distance(self.lat, self.lng)
            self.finished.emit(distance, snap_lat, snap_lng)
        except Exception as e:
            self.error.emit(str(e))


class LandCoverWorker(QThread):
    """Background worker for land cover analysis."""

    finished = pyqtSignal(dict)  # classification result
    error = pyqtSignal(str)

    def __init__(self, pixmap, lat, lng, zoom, radius_m=500, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.lat = lat
        self.lng = lng
        self.zoom = zoom
        self.radius_m = radius_m

    def run(self):
        try:
            result = analyze_landcover(
                self.pixmap, self.lat, self.lng, self.zoom, self.radius_m,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class WaybackLoader(QThread):
    """Background worker to find summer Wayback version by capture date."""

    result_ready = pyqtSignal(object)  # (release_num, date_str, metadata_url) or None
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, lat=None, lng=None, parent=None):
        super().__init__(parent)
        self.lat = lat
        self.lng = lng

    def run(self):
        try:
            if self.lat is not None and self.lng is not None:
                result = fetch_wayback_summer_by_capture(
                    self.lat, self.lng,
                    progress_callback=lambda msg: self.progress.emit(msg),
                )
            else:
                result = fetch_wayback_summer_version()
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class EvaluationPanel(QWidget):
    """Panel for risk evaluation with 4 sliders."""

    evaluation_saved = pyqtSignal()
    road_line_requested = pyqtSignal(float, float, float, float, float)  # site_lat, site_lng, road_lat, road_lng, distance_m
    road_line_cleared = pyqtSignal()
    analysis_circle_requested = pyqtSignal(float, float, float)  # lat, lng, radius_m
    analysis_circle_cleared = pyqtSignal()
    landcover_analysis_requested = pyqtSignal(int)  # radius_m

    CRITERIA = [
        ("road_proximity", "Road Proximity", "Distance from roads (1=Far, 5=Adjacent)"),
        ("accessibility", "Accessibility", "Ease of access (1=Difficult, 5=Very Easy)"),
        ("vegetation_cover", "Vegetation Cover", "Natural vegetation (1=Dense, 5=None)"),
        ("development_signs", "Development Signs", "Construction/development (1=None, 5=Heavy)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_site = None
        self.current_evaluation = None
        self._loading = False
        self._last_road_distance = None
        self._last_road_snap = (None, None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.sliders = {}
        self._road_worker = None
        self._landcover_worker = None

        # Grid for sliders (some hidden but kept in hierarchy for data)
        slider_grid = QGridLayout()
        slider_grid.setSpacing(4)
        for idx, (key, label, tooltip) in enumerate(self.CRITERIA):
            group = QGroupBox(label)
            group.setToolTip(tooltip)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(6, 2, 6, 2)

            slider_row = QHBoxLayout()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(1)
            slider.setMaximum(5)
            slider.setValue(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setTickInterval(1)
            slider.valueChanged.connect(self._update_risk_display)
            slider.valueChanged.connect(self._auto_save)

            value_label = QLabel("1")
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))

            slider_row.addWidget(slider)
            slider_row.addWidget(value_label)
            group_layout.addLayout(slider_row)

            if key == "road_proximity":
                measure_row = QHBoxLayout()
                self.measure_btn = QPushButton("Measure")
                self.measure_btn.setToolTip("Auto-measure distance to nearest road via OSRM")
                self.measure_btn.clicked.connect(self._measure_road_distance)
                self.road_distance_label = QLabel("")
                measure_row.addWidget(self.measure_btn)
                measure_row.addWidget(self.road_distance_label, 1)
                group_layout.addLayout(measure_row)

            self.sliders[key] = slider
            slider_grid.addWidget(group, idx // 2, idx % 2)
            if key in ("accessibility", "development_signs"):
                group.setVisible(False)

        layout.addLayout(slider_grid)

        # Land Cover Analysis section
        lc_group = QGroupBox("Land Cover Analysis")
        lc_layout = QVBoxLayout(lc_group)
        lc_layout.setContentsMargins(6, 2, 6, 2)
        lc_layout.setSpacing(4)

        lc_controls = QHBoxLayout()
        lc_controls.addWidget(QLabel("Radius:"))
        self.lc_radius_combo = QComboBox()
        self.lc_radius_combo.addItems(["250m", "500m", "1km"])
        self.lc_radius_combo.setCurrentIndex(1)  # 500m default
        lc_controls.addWidget(self.lc_radius_combo)
        self.lc_analyze_btn = QPushButton("Analyze")
        self.lc_analyze_btn.setToolTip("Analyze land cover from satellite imagery")
        self.lc_analyze_btn.clicked.connect(self._request_landcover_analysis)
        lc_controls.addWidget(self.lc_analyze_btn)
        self.lc_status_label = QLabel("")
        lc_controls.addWidget(self.lc_status_label, 1)
        lc_layout.addLayout(lc_controls)

        # Result bars
        self.lc_labels = {}
        self.lc_bars = {}
        lc_result_grid = QGridLayout()
        lc_result_grid.setSpacing(2)
        lc_classes = [
            ("dense_veg", "Dense Vegetation", "#228B22"),
            ("sparse_veg", "Sparse Vegetation", "#90EE90"),
            ("bare", "Bare Rock/Soil", "#D2B48C"),
            ("built", "Built-up/Paved", "#808080"),
            ("water", "Water", "#4169E1"),
        ]
        for row, (key, label, color) in enumerate(lc_classes):
            name_label = QLabel(label)
            name_label.setMinimumWidth(110)
            lc_result_grid.addWidget(name_label, row, 0)

            bar = QFrame()
            bar.setFixedHeight(14)
            bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            bar.setMinimumWidth(0)
            bar.setMaximumWidth(0)
            lc_result_grid.addWidget(bar, row, 1)
            self.lc_bars[key] = bar

            pct_label = QLabel("")
            pct_label.setMinimumWidth(35)
            lc_result_grid.addWidget(pct_label, row, 2)
            self.lc_labels[key] = pct_label

        lc_result_grid.setColumnStretch(1, 1)
        lc_layout.addLayout(lc_result_grid)
        layout.addWidget(lc_group)

        # Bottom row: risk display + notes
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(4)

        # Risk display
        risk_group = QGroupBox("Overall Risk")
        risk_layout = QHBoxLayout(risk_group)
        risk_layout.setContentsMargins(6, 2, 6, 2)
        self.risk_score_label = QLabel("Score: 4")
        self.risk_level_label = QLabel("Level: LOW")
        self.risk_level_label.setStyleSheet("font-weight: bold;")
        risk_layout.addWidget(self.risk_score_label)
        risk_layout.addWidget(self.risk_level_label)
        bottom_layout.addWidget(risk_group)

        # Notes
        notes_group = QGroupBox("Evaluator Notes")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setContentsMargins(6, 2, 6, 2)
        self.notes_text = QTextEdit()
        self.notes_text.textChanged.connect(self._auto_save)
        notes_layout.addWidget(self.notes_text)
        bottom_layout.addWidget(notes_group, 1)

        layout.addLayout(bottom_layout)

    def _update_risk_display(self):
        values = {key: slider.value() for key, slider in self.sliders.items()}
        score = calculate_risk_score(**values)
        level = get_risk_level(score)

        self.risk_score_label.setText(f"Score: {score}")
        self.risk_level_label.setText(f"Level: {level}")

        colors = {
            "LOW": "green",
            "MODERATE": "orange",
            "HIGH": "red",
            "CRITICAL": "darkred",
        }
        color = colors.get(level, "black")
        self.risk_level_label.setStyleSheet(f"font-weight: bold; color: {color};")

    def _update_road_distance_label(self, distance_m):
        if distance_m is None:
            self.road_distance_label.setText("")
        elif distance_m >= 1000:
            self.road_distance_label.setText(f"{distance_m / 1000:.1f}km")
        else:
            self.road_distance_label.setText(f"{distance_m:.0f}m")

    def set_site(self, site):
        self._loading = True
        self.current_site = site
        self._last_road_distance = None
        self._last_road_snap = (None, None)
        if site:
            try:
                ev = (RiskEvaluation
                      .select()
                      .where(RiskEvaluation.site == site)
                      .order_by(RiskEvaluation.evaluated_at.desc())
                      .get())
                self.current_evaluation = ev
                self.sliders["road_proximity"].setValue(ev.road_proximity)
                self.sliders["accessibility"].setValue(ev.accessibility)
                self.sliders["vegetation_cover"].setValue(ev.vegetation_cover)
                self.sliders["development_signs"].setValue(ev.development_signs)
                self.notes_text.setPlainText(ev.evaluator_notes or "")
                self._last_road_distance = ev.road_distance
                self._last_road_snap = (ev.road_snap_lat, ev.road_snap_lng)
                self._update_road_distance_label(ev.road_distance)
                self._restore_landcover_results(ev)
                if ev.road_snap_lat is not None and ev.road_snap_lng is not None:
                    self.road_line_requested.emit(
                        site.latitude, site.longitude,
                        ev.road_snap_lat, ev.road_snap_lng,
                        float(ev.road_distance or 0),
                    )
                else:
                    self.road_line_cleared.emit()
                if ev.landcover_analyzed_at is not None:
                    radius = ev.landcover_radius_m or 500
                    self.analysis_circle_requested.emit(
                        site.latitude, site.longitude, float(radius),
                    )
                else:
                    self.analysis_circle_cleared.emit()
            except RiskEvaluation.DoesNotExist:
                self.current_evaluation = None
                self._reset_sliders()
                self.road_line_cleared.emit()
                self.analysis_circle_cleared.emit()
        else:
            self.current_evaluation = None
            self._reset_sliders()
            self.road_line_cleared.emit()
            self.analysis_circle_cleared.emit()
        self._loading = False

    def _reset_sliders(self):
        for slider in self.sliders.values():
            slider.setValue(1)
        self.notes_text.clear()
        self.road_distance_label.setText("")
        self._last_road_distance = None
        self._last_road_snap = (None, None)
        self._clear_landcover_display()

    def _measure_road_distance(self):
        if not self.current_site:
            QMessageBox.warning(self, "Warning", "No site selected.")
            return

        self.measure_btn.setEnabled(False)
        self.road_distance_label.setText("Measuring...")

        self._road_worker = RoadDistanceWorker(
            self.current_site.latitude, self.current_site.longitude
        )
        self._road_worker.finished.connect(self._on_measure_finished)
        self._road_worker.error.connect(self._on_measure_error)
        self._road_worker.start()

    def _on_measure_finished(self, distance_m, snap_lat, snap_lng):
        self._last_road_distance = distance_m
        self._last_road_snap = (snap_lat, snap_lng)
        score = road_distance_to_score(distance_m)
        self.sliders["road_proximity"].setValue(score)
        self._update_road_distance_label(distance_m)
        self._auto_save()
        self.road_line_requested.emit(
            self.current_site.latitude, self.current_site.longitude,
            snap_lat, snap_lng, distance_m,
        )
        self.measure_btn.setEnabled(True)
        self._road_worker = None

    def _on_measure_error(self, error_msg):
        self.road_distance_label.setText("Error")
        self.measure_btn.setEnabled(True)
        QMessageBox.warning(self, "Measurement Error",
                            f"Failed to measure road distance:\n{error_msg}")
        self._road_worker = None

    def _get_radius_m(self):
        """Get selected analysis radius in meters."""
        text = self.lc_radius_combo.currentText()
        if text == "250m":
            return 250
        elif text == "1km":
            return 1000
        return 500

    def _request_landcover_analysis(self):
        if not self.current_site:
            QMessageBox.warning(self, "Warning", "No site selected.")
            return
        self.lc_analyze_btn.setEnabled(False)
        self.lc_status_label.setText("Analyzing...")
        self.landcover_analysis_requested.emit(self._get_radius_m())

    def start_landcover_worker(self, pixmap, lat, lng, zoom, radius_m):
        """Start the land cover analysis worker with a captured pixmap."""
        self._landcover_worker = LandCoverWorker(pixmap, lat, lng, zoom, radius_m)
        self._landcover_worker.finished.connect(self._on_landcover_finished)
        self._landcover_worker.error.connect(self._on_landcover_error)
        self._landcover_worker.start()

    def _on_landcover_finished(self, results):
        self.lc_analyze_btn.setEnabled(True)
        self.lc_status_label.setText("")
        self._display_landcover_results(results)
        self._apply_landcover_to_sliders(results)
        self._save_landcover_results(results)
        self._landcover_worker = None

    def _on_landcover_error(self, error_msg):
        self.lc_analyze_btn.setEnabled(True)
        self.lc_status_label.setText("Error")
        QMessageBox.warning(self, "Analysis Error",
                            f"Land cover analysis failed:\n{error_msg}")
        self._landcover_worker = None

    def _display_landcover_results(self, results):
        """Update the result bars and percentage labels."""
        max_bar_width = 150
        for key in self.lc_labels:
            pct = results.get(key, 0)
            self.lc_labels[key].setText(f"{pct}%")
            bar_width = int(pct * max_bar_width / 100)
            self.lc_bars[key].setMaximumWidth(max(bar_width, 0))
            self.lc_bars[key].setMinimumWidth(max(bar_width, 0))

    def _apply_landcover_to_sliders(self, results):
        """Auto-adjust vegetation_cover and development_signs sliders."""
        total_veg = results.get("dense_veg", 0) + results.get("sparse_veg", 0)
        # vegetation_cover: 1=Dense(>60%), 2=(40-60%), 3=(20-40%), 4=(5-20%), 5=None(<5%)
        if total_veg > 60:
            veg_score = 1
        elif total_veg > 40:
            veg_score = 2
        elif total_veg > 20:
            veg_score = 3
        elif total_veg > 5:
            veg_score = 4
        else:
            veg_score = 5
        self.sliders["vegetation_cover"].setValue(veg_score)

        built_pct = results.get("built", 0)
        # development_signs: 1=None(<5%), 2=(5-15%), 3=(15-30%), 4=(30-50%), 5=Heavy(>50%)
        if built_pct < 5:
            dev_score = 1
        elif built_pct < 15:
            dev_score = 2
        elif built_pct < 30:
            dev_score = 3
        elif built_pct < 50:
            dev_score = 4
        else:
            dev_score = 5
        self.sliders["development_signs"].setValue(dev_score)

    def _save_landcover_results(self, results):
        """Save land cover results to current evaluation."""
        if not self.current_evaluation:
            self._auto_save()  # creates evaluation if needed
        if self.current_evaluation:
            ev = self.current_evaluation
            ev.landcover_dense_veg = results.get("dense_veg", 0)
            ev.landcover_sparse_veg = results.get("sparse_veg", 0)
            ev.landcover_bare = results.get("bare", 0)
            ev.landcover_built = results.get("built", 0)
            ev.landcover_water = results.get("water", 0)
            ev.landcover_radius_m = self._get_radius_m()
            ev.landcover_analyzed_at = datetime.datetime.now()
            ev.save()

    def _clear_landcover_display(self):
        """Clear land cover result bars and labels."""
        for key in self.lc_labels:
            self.lc_labels[key].setText("")
            self.lc_bars[key].setMaximumWidth(0)
            self.lc_bars[key].setMinimumWidth(0)
        self.lc_status_label.setText("")

    def _restore_landcover_results(self, ev):
        """Restore previously saved landcover results to the UI."""
        if ev.landcover_analyzed_at is not None:
            results = {
                "dense_veg": ev.landcover_dense_veg or 0,
                "sparse_veg": ev.landcover_sparse_veg or 0,
                "bare": ev.landcover_bare or 0,
                "built": ev.landcover_built or 0,
                "water": ev.landcover_water or 0,
            }
            self._display_landcover_results(results)
            # Restore radius combo
            radius = ev.landcover_radius_m or 500
            if radius == 250:
                self.lc_radius_combo.setCurrentIndex(0)
            elif radius == 1000:
                self.lc_radius_combo.setCurrentIndex(2)
            else:
                self.lc_radius_combo.setCurrentIndex(1)
        else:
            self._clear_landcover_display()

    def _auto_save(self):
        if self._loading or not self.current_site:
            return

        values = {key: slider.value() for key, slider in self.sliders.items()}
        score = calculate_risk_score(**values)
        level = get_risk_level(score)

        snap_lat, snap_lng = self._last_road_snap
        if self.current_evaluation:
            ev = self.current_evaluation
            ev.road_proximity = values["road_proximity"]
            ev.road_distance = self._last_road_distance
            ev.road_snap_lat = snap_lat
            ev.road_snap_lng = snap_lng
            ev.accessibility = values["accessibility"]
            ev.vegetation_cover = values["vegetation_cover"]
            ev.development_signs = values["development_signs"]
            ev.overall_risk = score
            ev.risk_level = level
            ev.evaluator_notes = self.notes_text.toPlainText() or None
            ev.evaluated_at = datetime.datetime.now()
            ev.save()
        else:
            ev = RiskEvaluation.create(
                site=self.current_site,
                road_proximity=values["road_proximity"],
                road_distance=self._last_road_distance,
                road_snap_lat=snap_lat,
                road_snap_lng=snap_lng,
                accessibility=values["accessibility"],
                vegetation_cover=values["vegetation_cover"],
                development_signs=values["development_signs"],
                overall_risk=score,
                risk_level=level,
                evaluator_notes=self.notes_text.toPlainText() or None,
            )
            self.current_evaluation = ev

        self.evaluation_saved.emit()


class PhotoGalleryWidget(QWidget):
    """Widget for displaying screenshots and site photos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_site = None

        layout = QVBoxLayout(self)

        # Screenshots section
        ss_group = QGroupBox("Screenshots")
        ss_layout = QVBoxLayout(ss_group)
        self.screenshot_scroll = QScrollArea()
        self.screenshot_scroll.setWidgetResizable(True)
        self.screenshot_container = QWidget()
        self.screenshot_grid = QGridLayout(self.screenshot_container)
        self.screenshot_scroll.setWidget(self.screenshot_container)
        self.screenshot_scroll.setMinimumHeight(0)
        ss_layout.addWidget(self.screenshot_scroll)
        layout.addWidget(ss_group)

        # Photos section
        photo_group = QGroupBox("Site Photos")
        photo_layout = QVBoxLayout(photo_group)

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("Import Photos...")
        self.import_btn.clicked.connect(self._import_photos)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addStretch()
        photo_layout.addLayout(btn_layout)

        self.photo_scroll = QScrollArea()
        self.photo_scroll.setWidgetResizable(True)
        self.photo_container = QWidget()
        self.photo_grid = QGridLayout(self.photo_container)
        self.photo_scroll.setWidget(self.photo_container)
        self.photo_scroll.setMinimumHeight(0)
        photo_layout.addWidget(self.photo_scroll)
        layout.addWidget(photo_group)

        layout.addStretch()

    def set_site(self, site):
        self.current_site = site
        self._load_screenshots()
        self._load_photos()

    def _clear_grid(self, grid):
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _load_screenshots(self):
        self._clear_grid(self.screenshot_grid)
        if not self.current_site:
            return
        screenshots = (SiteScreenshot
                       .select()
                       .where(SiteScreenshot.site == self.current_site)
                       .order_by(SiteScreenshot.captured_at.desc()))
        col = 0
        for ss in screenshots:
            if os.path.exists(ss.file_path):
                thumb = self._make_thumbnail(ss.file_path, ss.map_type)
                self.screenshot_grid.addWidget(thumb, 0, col)
                col += 1

    def _load_photos(self):
        self._clear_grid(self.photo_grid)
        if not self.current_site:
            return
        photos = (SitePhoto
                  .select()
                  .where(SitePhoto.site == self.current_site)
                  .order_by(SitePhoto.created_at.desc()))
        col = 0
        row = 0
        for photo in photos:
            if os.path.exists(photo.file_path):
                thumb = self._make_thumbnail(photo.file_path, photo.description or "")
                self.photo_grid.addWidget(thumb, row, col)
                col += 1
                if col >= 4:
                    col = 0
                    row += 1

    def _make_thumbnail(self, filepath, label_text=""):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        pixmap = QPixmap(filepath)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        if label_text:
            text_label = QLabel(label_text)
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_label.setMaximumWidth(120)
            text_label.setWordWrap(True)
            layout.addWidget(text_label)

        return container

    def _import_photos(self):
        if not self.current_site:
            QMessageBox.warning(self, "Warning", "No site selected.")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Photos", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)"
        )
        if not files:
            return

        import shutil
        photos_dir = get_photos_dir()
        for filepath in files:
            filename = os.path.basename(filepath)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
            dest = os.path.join(photos_dir, timestamp + filename)
            shutil.copy2(filepath, dest)
            SitePhoto.create(
                site=self.current_site,
                file_path=dest,
                photo_type="field",
            )

        self._load_photos()

    def refresh(self):
        self._load_screenshots()
        self._load_photos()
