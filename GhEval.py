import logging
import math

from PyQt6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QLabel, QComboBox,
    QSplitter, QWidget, QVBoxLayout, QMessageBox,
    QTabWidget, QPushButton,
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence

from GhCommons import (
    APP_TITLE, PROGRAM_VERSION, COMPANY_NAME, PROGRAM_NAME,
    MAP_TYPES, DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_ZOOM,
    road_distance_to_score,
)
from GhModels import GeoHeritageSite, db
from GhComponents import (
    MapWidget, SiteListWidget, SiteInfoPanel,
    EvaluationPanel, PhotoGalleryWidget, WaybackLoader,
    RoadDistanceWorker,
)
from GhDialogs import SiteEditDialog, SettingsDialog, ReportDialog

logger = logging.getLogger(__name__)


class GhEvalMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(COMPANY_NAME, PROGRAM_NAME)
        self.current_site = None

        self.setWindowTitle(f"{APP_TITLE} v{PROGRAM_VERSION}")
        self.setMinimumSize(1024, 768)

        self._create_actions()
        self._create_menubar()
        self._create_toolbar()
        self._create_statusbar()
        self._create_central_widget()
        self._connect_signals()
        self._restore_geometry()

    # ── Actions ──────────────────────────────────────────────

    def _create_actions(self):
        self.action_new_site = QAction("&New Site", self)
        self.action_new_site.setShortcut(QKeySequence("Ctrl+N"))
        self.action_new_site.setStatusTip("Create a new geoheritage site")

        self.action_delete_site = QAction("&Delete Site", self)
        self.action_delete_site.setStatusTip("Delete selected site")

        self.action_capture = QAction("Capture &Screenshot", self)
        self.action_capture.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_capture.setStatusTip("Capture map screenshot")

        self.action_settings = QAction("S&ettings...", self)
        self.action_settings.setStatusTip("Open settings dialog")

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.action_exit.triggered.connect(self.close)

        self.action_about = QAction("&About", self)
        self.action_about.triggered.connect(self._show_about)

        self.action_export_report = QAction("Export &Report...", self)
        self.action_export_report.setStatusTip("Export evaluation report")

    # ── Menubar ──────────────────────────────────────────────

    def _create_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.action_new_site)
        file_menu.addAction(self.action_delete_site)
        file_menu.addSeparator()
        file_menu.addAction(self.action_export_report)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        site_menu = menubar.addMenu("&Site")
        site_menu.addAction(self.action_capture)

        view_menu = menubar.addMenu("&View")
        self.map_type_group = QActionGroup(self)
        self.map_type_actions = []
        for mt in MAP_TYPES:
            action = QAction(mt, self)
            action.setCheckable(True)
            action.setData(mt)
            action.triggered.connect(self._on_map_type_changed)
            self.map_type_group.addAction(action)
            self.map_type_actions.append(action)
            view_menu.addAction(action)
        if self.map_type_actions:
            self.map_type_actions[0].setChecked(True)

        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self.action_settings)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.action_about)

    # ── Toolbar ──────────────────────────────────────────────

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(self.action_new_site)
        toolbar.addAction(self.action_delete_site)
        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" Map: "))
        self.map_type_combo = QComboBox()
        self.map_type_combo.addItems(MAP_TYPES)
        self.map_type_combo.currentTextChanged.connect(self._on_map_type_combo_changed)
        toolbar.addWidget(self.map_type_combo)

        toolbar.addSeparator()
        toolbar.addAction(self.action_capture)

    # ── Statusbar ────────────────────────────────────────────

    def _create_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    # ── Central widget with splitters ────────────────────────

    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Vertical splitter: top (list+map) / bottom (tabs)
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Horizontal splitter: left (site list) / right (map)
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: site list
        self.site_list = SiteListWidget()
        self.h_splitter.addWidget(self.site_list)

        # Right panel: map
        self.map_widget = MapWidget()
        self.h_splitter.addWidget(self.map_widget)

        self.h_splitter.setStretchFactor(0, 1)
        self.h_splitter.setStretchFactor(1, 4)

        self.v_splitter.addWidget(self.h_splitter)

        # Bottom panel: tabs
        self.tab_widget = QTabWidget()

        self.info_panel = SiteInfoPanel()
        self.tab_widget.addTab(self.info_panel, "Info")

        self.eval_panel = EvaluationPanel()
        self.tab_widget.addTab(self.eval_panel, "Evaluation")

        self.photo_gallery = PhotoGalleryWidget()
        self.tab_widget.addTab(self.photo_gallery, "Photos")

        self.analyze_btn = QPushButton("  Analyze  ")
        self.analyze_btn.setToolTip("Run full analysis: road distance + vegetation")
        self.tab_widget.setCornerWidget(self.analyze_btn)

        self.v_splitter.addWidget(self.tab_widget)
        self.v_splitter.setStretchFactor(0, 5)
        self.v_splitter.setStretchFactor(1, 1)
        self.v_splitter.setSizes([600, 160])

        main_layout.addWidget(self.v_splitter)

        # Load site list
        self.site_list.load_sites()

    # ── Signal connections ───────────────────────────────────

    def _connect_signals(self):
        self.action_new_site.triggered.connect(self._new_site)
        self.action_delete_site.triggered.connect(self._delete_site)
        self.action_capture.triggered.connect(self._capture_screenshot)
        self.action_settings.triggered.connect(self._open_settings)
        self.action_export_report.triggered.connect(self._open_report)

        self.site_list.site_selected.connect(self._on_site_selected)
        self.map_widget.map_clicked.connect(self._on_map_clicked)
        self.map_widget.add_site_requested.connect(self._on_add_site_at)
        self.map_widget.zoom_changed.connect(self._on_zoom_changed)
        self.map_widget.map_ready.connect(self._on_map_ready)
        self.map_widget.marker_clicked.connect(self._on_marker_clicked)
        self.map_widget.screenshot_saved.connect(
            lambda path: self._capture_screenshot() if not path else
            self.statusbar.showMessage(f"Screenshot saved: {path}", 5000)
        )
        self.info_panel.site_updated.connect(self._on_site_info_updated)
        self.eval_panel.evaluation_saved.connect(
            lambda: self.statusbar.showMessage("Evaluation saved.", 3000)
        )
        self.eval_panel.road_line_requested.connect(self.map_widget.show_road_line)
        self.eval_panel.road_line_cleared.connect(self.map_widget.clear_road_line)
        self.eval_panel.analysis_circle_requested.connect(self.map_widget.show_analysis_circle)
        self.eval_panel.analysis_circle_cleared.connect(self.map_widget.clear_analysis_circle)
        self.eval_panel.landcover_analysis_requested.connect(self._on_landcover_requested)
        self.analyze_btn.clicked.connect(self._run_full_analysis)

    # ── Event handlers ───────────────────────────────────────

    def _on_map_ready(self):
        self._refresh_markers()
        lat = self.settings.value("map/default_lat", DEFAULT_LATITUDE, type=float)
        lng = self.settings.value("map/default_lng", DEFAULT_LONGITUDE, type=float)
        zoom = self.settings.value("map/default_zoom", DEFAULT_ZOOM, type=int)
        self.map_widget.goto(lat, lng, zoom)
        logger.info("Map ready")

    def _on_site_selected(self, site):
        self.current_site = site
        self.info_panel.set_site(site)
        self.eval_panel.set_site(site)
        self.photo_gallery.set_site(site)
        if site:
            self.map_widget.highlight_site_marker(site.id)
            self.map_widget.goto(site.latitude, site.longitude, 15)
            self.statusbar.showMessage(
                f"{site.site_name} | {site.latitude:.6f}, {site.longitude:.6f}"
            )
        else:
            self.statusbar.showMessage("No site selected")

    def _on_map_clicked(self, lat, lng):
        self.statusbar.showMessage(f"Clicked: {lat:.6f}, {lng:.6f}")

    def _on_add_site_at(self, lat, lng):
        dialog = SiteEditDialog(self, lat=lat, lng=lng)
        if dialog.exec():
            data = dialog.get_site_data()
            site = GeoHeritageSite.create(**data)
            self.site_list.load_sites()
            self.site_list.select_site_by_id(site.id)
            self._refresh_markers()
            self.statusbar.showMessage(f"Created site: {site.site_name}", 3000)

    def _on_zoom_changed(self, zoom):
        current_msg = self.statusbar.currentMessage()
        if "|" in current_msg:
            base = current_msg.split("|")[0].strip()
            self.statusbar.showMessage(f"{base} | Zoom: {zoom}")

    def _on_marker_clicked(self, site_id):
        self.site_list.select_site_by_id(site_id)

    def _on_map_type_changed(self):
        action = self.map_type_group.checkedAction()
        if action:
            map_type = action.data()
            if map_type == "SKYVIEW (Summer)":
                self.map_widget.set_map_type("SKYVIEW_SUMMER")
                self._load_summer_wayback()
            else:
                self.map_widget.set_map_type(map_type)
            self.map_type_combo.blockSignals(True)
            self.map_type_combo.setCurrentText(map_type)
            self.map_type_combo.blockSignals(False)

    def _on_map_type_combo_changed(self, map_type):
        if map_type == "SKYVIEW (Summer)":
            self.map_widget.set_map_type("SKYVIEW_SUMMER")
            self._load_summer_wayback()
        else:
            self.map_widget.set_map_type(map_type)
        for action in self.map_type_actions:
            if action.data() == map_type:
                action.setChecked(True)
                break

    # ── Site operations ──────────────────────────────────────

    def _new_site(self):
        dialog = SiteEditDialog(self)
        if dialog.exec():
            data = dialog.get_site_data()
            site = GeoHeritageSite.create(**data)
            self.site_list.load_sites()
            self.site_list.select_site_by_id(site.id)
            self._refresh_markers()
            self.statusbar.showMessage(f"Created site: {site.site_name}", 3000)

    def _on_site_info_updated(self):
        if not self.current_site:
            return
        site_id = self.current_site.id
        self.site_list.list_widget.blockSignals(True)
        self.site_list.load_sites()
        self.site_list.select_site_by_id(site_id)
        self.site_list.list_widget.blockSignals(False)
        self._refresh_markers()

    def _delete_site(self):
        if not self.current_site:
            QMessageBox.information(self, "Info", "No site selected to delete.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete site '{self.current_site.site_name}' and all associated data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            name = self.current_site.site_name
            self.current_site.delete_instance(recursive=True)
            self.current_site = None
            self.site_list.load_sites()
            self._on_site_selected(None)
            self._refresh_markers()
            self.statusbar.showMessage(f"Deleted site: {name}", 3000)

    # ── Screenshot ───────────────────────────────────────────

    def _capture_screenshot(self):
        if not self.current_site:
            QMessageBox.information(self, "Info", "Select a site first to capture screenshot.")
            return
        record = self.map_widget.capture_screenshot(self.current_site)
        if record:
            self.photo_gallery.refresh()
            self.statusbar.showMessage("Screenshot captured.", 3000)

    # ── Land cover analysis ────────────────────────────────────

    def _on_landcover_requested(self, radius_m):
        if not self.current_site:
            return
        # Switch to satellite view and zoom 17 for best analysis
        self.map_widget.set_map_type("SKYVIEW")
        self.map_widget.show_analysis_circle(
            self.current_site.latitude, self.current_site.longitude, radius_m,
        )
        self.map_widget.goto(
            self.current_site.latitude, self.current_site.longitude, 17,
        )
        # Delay capture to allow tiles to load
        QTimer.singleShot(2000, lambda: self._capture_for_landcover(radius_m))

    def _capture_for_landcover(self, radius_m):
        if not self.current_site:
            return
        pixmap = self.map_widget.web_view.grab()
        self.eval_panel.start_landcover_worker(
            pixmap,
            self.current_site.latitude,
            self.current_site.longitude,
            self.map_widget.current_zoom,
            radius_m,
        )
        self.statusbar.showMessage("Land cover analysis running...", 5000)

    # ── Full analysis ─────────────────────────────────────────

    def _run_full_analysis(self):
        if not self.current_site:
            QMessageBox.information(self, "Info", "Select a site first.")
            return

        self.analyze_btn.setEnabled(False)
        self._analysis_worker = None

        # Switch to satellite view
        self.map_type_combo.setCurrentText("SKYVIEW")

        # Step 1: Road distance
        self.statusbar.showMessage("Step 1/3: Measuring road distance...")
        site = self.current_site
        worker = RoadDistanceWorker(site.latitude, site.longitude)
        worker.finished.connect(self._analysis_road_done)
        worker.error.connect(self._analysis_error)
        self._analysis_worker = worker
        worker.start()

    def _analysis_road_done(self, distance_m, snap_lat, snap_lng):
        site = self.current_site
        if not site:
            return self._analysis_finish()

        # Update eval panel
        ep = self.eval_panel
        ep._last_road_distance = distance_m
        ep._last_road_snap = (snap_lat, snap_lng)
        ep.sliders["road_proximity"].setValue(road_distance_to_score(distance_m))
        ep._update_road_distance_label(distance_m)
        ep._auto_save()

        # Show road line
        self.map_widget.show_road_line(
            site.latitude, site.longitude, snap_lat, snap_lng,
        )

        # Step 2: Zoom to show road → capture
        self.statusbar.showMessage("Step 2/3: Capturing road view...")
        zoom = self._zoom_for_meters(distance_m, site.latitude)
        self.map_widget.goto(site.latitude, site.longitude, zoom)
        QTimer.singleShot(2500, self._analysis_capture_road)

    def _analysis_capture_road(self):
        site = self.current_site
        if not site:
            return self._analysis_finish()

        self.map_widget.capture_screenshot(site)

        # Clear road line for clean vegetation capture
        self.map_widget.clear_road_line()

        # Step 3: Zoom to vegetation radius → capture + analyze
        self.statusbar.showMessage("Step 3/3: Analyzing vegetation...")
        radius_m = self.eval_panel._get_radius_m()
        self.map_widget.show_analysis_circle(
            site.latitude, site.longitude, radius_m,
        )
        zoom = self._zoom_for_meters(radius_m, site.latitude)
        self.map_widget.goto(site.latitude, site.longitude, zoom)
        QTimer.singleShot(2500, lambda: self._analysis_capture_veg(radius_m))

    def _analysis_capture_veg(self, radius_m):
        site = self.current_site
        if not site:
            return self._analysis_finish()

        self.map_widget.capture_screenshot(site)

        # Run land cover analysis on current view
        pixmap = self.map_widget.web_view.grab()
        self.eval_panel.start_landcover_worker(
            pixmap, site.latitude, site.longitude,
            self.map_widget.current_zoom, radius_m,
        )

        # Finish when landcover completes
        worker = self.eval_panel._landcover_worker
        if worker:
            worker.finished.connect(lambda _: self._analysis_finish())
            worker.error.connect(lambda _: self._analysis_finish())
        else:
            self._analysis_finish()

    def _analysis_finish(self):
        self.analyze_btn.setEnabled(True)
        self.photo_gallery.refresh()
        self.map_widget.clear_analysis_circle()
        # Restore road line
        site = self.current_site
        ep = self.eval_panel
        if site and ep._last_road_snap[0] is not None:
            self.map_widget.show_road_line(
                site.latitude, site.longitude,
                ep._last_road_snap[0], ep._last_road_snap[1],
            )
        self.statusbar.showMessage("Analysis complete.", 5000)
        self._analysis_worker = None

    def _analysis_error(self, error_msg):
        self.analyze_btn.setEnabled(True)
        self.statusbar.showMessage(f"Analysis error: {error_msg}", 5000)
        self._analysis_worker = None

    def _zoom_for_meters(self, meters, lat):
        """Calculate zoom level to fit `meters` radius in the map view."""
        if meters <= 0:
            return 17
        cos_lat = math.cos(math.radians(lat))
        # ~800px view, show 2*meters with 30% margin
        view_meters = meters * 2.6
        z = math.log2(800 * 156543.03392 * cos_lat / view_meters)
        return max(1, min(19, int(z)))

    # ── Summer Wayback imagery ────────────────────────────────

    def _load_summer_wayback(self):
        self.statusbar.showMessage("Searching for summer imagery...")
        if self.current_site:
            lat, lng = self.current_site.latitude, self.current_site.longitude
        else:
            lat = self.settings.value("map/default_lat", DEFAULT_LATITUDE, type=float)
            lng = self.settings.value("map/default_lng", DEFAULT_LONGITUDE, type=float)
        self._wayback_loader = WaybackLoader(lat, lng)
        self._wayback_loader.result_ready.connect(self._on_wayback_loaded)
        self._wayback_loader.progress.connect(
            lambda msg: self.statusbar.showMessage(msg)
        )
        self._wayback_loader.error.connect(
            lambda e: self.statusbar.showMessage(f"Wayback error: {e}", 5000)
        )
        self._wayback_loader.start()

    def _on_wayback_loaded(self, result):
        if result:
            release_num, date_str, metadata_url = result
            self.map_widget.set_wayback_version(release_num, date_str, metadata_url)
            self.statusbar.showMessage(f"Summer imagery: {date_str}", 5000)
        else:
            self.statusbar.showMessage("No summer imagery found", 5000)
        self._wayback_loader = None

    # ── Map markers ──────────────────────────────────────────

    def _refresh_markers(self):
        self.map_widget.clear_site_markers()
        for site in GeoHeritageSite.select():
            self.map_widget.add_site_marker(
                site.id, site.latitude, site.longitude, site.site_name
            )

    # ── Dialogs ──────────────────────────────────────────────

    def _open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def _open_report(self):
        dialog = ReportDialog(self)
        dialog.exec()

    # ── Window state ─────────────────────────────────────────

    def _restore_geometry(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def _show_about(self):
        QMessageBox.about(
            self,
            f"About {APP_TITLE}",
            f"<h3>{APP_TITLE}</h3>"
            f"<p>Version {PROGRAM_VERSION}</p>"
            f"<p>A tool for evaluating geoheritage site risk.</p>"
            f"<p>&copy; {COMPANY_NAME}</p>",
        )
