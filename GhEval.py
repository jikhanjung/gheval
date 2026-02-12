import logging

from PyQt6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QLabel, QComboBox,
    QSplitter, QWidget, QVBoxLayout, QMessageBox,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence

from GhCommons import (
    APP_TITLE, PROGRAM_VERSION, COMPANY_NAME, PROGRAM_NAME,
    MAP_TYPES, DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_ZOOM,
)
from GhModels import GeoHeritageSite, db
from GhComponents import (
    MapWidget, SiteListWidget, SiteInfoPanel,
    EvaluationPanel, PhotoGalleryWidget,
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

        self.action_save_site = QAction("&Save Site", self)
        self.action_save_site.setShortcut(QKeySequence("Ctrl+S"))
        self.action_save_site.setStatusTip("Save current site")

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
        file_menu.addAction(self.action_save_site)
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
        toolbar.addAction(self.action_save_site)
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

        self.v_splitter.addWidget(self.tab_widget)
        self.v_splitter.setStretchFactor(0, 3)
        self.v_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.v_splitter)

        # Load site list
        self.site_list.load_sites()

    # ── Signal connections ───────────────────────────────────

    def _connect_signals(self):
        self.action_new_site.triggered.connect(self._new_site)
        self.action_save_site.triggered.connect(self._edit_current_site)
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
        self.eval_panel.evaluation_saved.connect(
            lambda: self.statusbar.showMessage("Evaluation saved.", 3000)
        )

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
            self.map_widget.set_map_type(action.data())
            self.map_type_combo.blockSignals(True)
            self.map_type_combo.setCurrentText(action.data())
            self.map_type_combo.blockSignals(False)

    def _on_map_type_combo_changed(self, map_type):
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

    def _edit_current_site(self):
        if not self.current_site:
            QMessageBox.information(self, "Info", "No site selected to edit.")
            return
        dialog = SiteEditDialog(self, site=self.current_site)
        if dialog.exec():
            data = dialog.get_site_data()
            for key, value in data.items():
                setattr(self.current_site, key, value)
            self.current_site.save()
            self.site_list.load_sites()
            self.site_list.select_site_by_id(self.current_site.id)
            self._refresh_markers()
            self.statusbar.showMessage(f"Updated site: {self.current_site.site_name}", 3000)

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
