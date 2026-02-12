import os
import json
import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QSlider, QPushButton, QGroupBox, QFormLayout, QTextEdit,
    QComboBox, QSpinBox, QFileDialog, QScrollArea, QGridLayout,
    QSplitter, QFrame, QTabWidget, QLineEdit, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from GhCommons import (
    resource_path, DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_ZOOM,
    MAP_TYPES, get_screenshots_dir, calculate_risk_score, get_risk_level,
    get_photos_dir,
)
from GhMapBridge import MapBridge
from GhModels import (
    GeoHeritageSite, SiteScreenshot, RiskEvaluation, SitePhoto, db,
)


class MapWidget(QWidget):
    """Map display widget using QWebEngineView with Leaflet/OSM."""

    map_clicked = pyqtSignal(float, float)
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
        self.bridge = MapBridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.bridge.map_clicked.connect(self._on_map_clicked)
        self.bridge.zoom_changed.connect(self._on_zoom_changed)
        self.bridge.map_ready.connect(self._on_map_ready)
        self.bridge.marker_clicked.connect(self.marker_clicked.emit)

        html_path = resource_path(os.path.join("templates", "map_view.html"))
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))

        layout.addWidget(self.web_view)

    def _on_map_clicked(self, lat, lng):
        self.map_clicked.emit(lat, lng)

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
    """Panel displaying site information (read-only view in the tab)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.name_label = QLabel()
        self.coords_label = QLabel()
        self.address_label = QLabel()
        self.type_label = QLabel()
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(100)

        layout.addRow("Name:", self.name_label)
        layout.addRow("Coordinates:", self.coords_label)
        layout.addRow("Address:", self.address_label)
        layout.addRow("Type:", self.type_label)
        layout.addRow("Description:", self.desc_text)

    def set_site(self, site):
        if site:
            self.name_label.setText(site.site_name)
            self.coords_label.setText(f"{site.latitude:.6f}, {site.longitude:.6f}")
            self.address_label.setText(site.address or "")
            self.type_label.setText(site.site_type or "")
            self.desc_text.setPlainText(site.site_desc or "")
        else:
            self.name_label.setText("")
            self.coords_label.setText("")
            self.address_label.setText("")
            self.type_label.setText("")
            self.desc_text.clear()


class EvaluationPanel(QWidget):
    """Panel for risk evaluation with 4 sliders."""

    evaluation_saved = pyqtSignal()

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

        layout = QVBoxLayout(self)
        self.sliders = {}

        for key, label, tooltip in self.CRITERIA:
            group = QGroupBox(label)
            group.setToolTip(tooltip)
            group_layout = QHBoxLayout(group)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(1)
            slider.setMaximum(5)
            slider.setValue(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setTickInterval(1)
            slider.valueChanged.connect(self._update_risk_display)

            value_label = QLabel("1")
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))

            group_layout.addWidget(slider)
            group_layout.addWidget(value_label)
            self.sliders[key] = slider
            layout.addWidget(group)

        # Risk display
        risk_group = QGroupBox("Overall Risk")
        risk_layout = QHBoxLayout(risk_group)
        self.risk_score_label = QLabel("Score: 4")
        self.risk_level_label = QLabel("Level: LOW")
        self.risk_level_label.setStyleSheet("font-weight: bold;")
        risk_layout.addWidget(self.risk_score_label)
        risk_layout.addWidget(self.risk_level_label)
        layout.addWidget(risk_group)

        # Notes
        notes_group = QGroupBox("Evaluator Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_text = QTextEdit()
        self.notes_text.setMaximumHeight(80)
        notes_layout.addWidget(self.notes_text)
        layout.addWidget(notes_group)

        # Save button
        self.save_btn = QPushButton("Save Evaluation")
        self.save_btn.clicked.connect(self._save_evaluation)
        layout.addWidget(self.save_btn)

        layout.addStretch()

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

    def set_site(self, site):
        self.current_site = site
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
            except RiskEvaluation.DoesNotExist:
                self.current_evaluation = None
                self._reset_sliders()
        else:
            self.current_evaluation = None
            self._reset_sliders()

    def _reset_sliders(self):
        for slider in self.sliders.values():
            slider.setValue(1)
        self.notes_text.clear()

    def _save_evaluation(self):
        if not self.current_site:
            QMessageBox.warning(self, "Warning", "No site selected.")
            return

        values = {key: slider.value() for key, slider in self.sliders.items()}
        score = calculate_risk_score(**values)
        level = get_risk_level(score)

        if self.current_evaluation:
            ev = self.current_evaluation
            ev.road_proximity = values["road_proximity"]
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
        self.screenshot_scroll.setMinimumHeight(120)
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
        self.photo_scroll.setMinimumHeight(120)
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
