import os
import json
import csv
import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDoubleSpinBox, QComboBox, QPushButton, QLabel,
    QDialogButtonBox, QMessageBox, QGroupBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QProgressBar, QWidget, QListWidget,
)
from PyQt6.QtCore import Qt, QSettings

from GhCommons import (
    COMPANY_NAME, PROGRAM_NAME, DEFAULT_LATITUDE, DEFAULT_LONGITUDE,
    calculate_risk_score, get_risk_level, parse_coordinates,
)
from GhModels import GeoHeritageSite, RiskEvaluation, SiteScreenshot, SitePhoto


class SiteEditDialog(QDialog):
    """Dialog for creating/editing a geoheritage site."""

    def __init__(self, parent=None, site=None, lat=None, lng=None):
        super().__init__(parent)
        self.site = site
        self.setWindowTitle("Edit Site" if site else "New Site")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        layout.addRow("Site Name:", self.name_edit)

        # Coordinate paste input
        coord_input_layout = QHBoxLayout()
        self.coord_input = QLineEdit()
        self.coord_input.setPlaceholderText(
            "e.g. 37.5665, 126.978  or  37°33'59\"N 126°58'41\"E"
        )
        self.coord_input.returnPressed.connect(self._apply_coord_input)
        coord_input_layout.addWidget(self.coord_input, 1)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_coord_input)
        coord_input_layout.addWidget(apply_btn)
        layout.addRow("Coords Input:", coord_input_layout)

        coord_layout = QHBoxLayout()
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lat_spin.setDecimals(6)
        self.lat_spin.setValue(DEFAULT_LATITUDE)
        self.lng_spin = QDoubleSpinBox()
        self.lng_spin.setRange(-180.0, 180.0)
        self.lng_spin.setDecimals(6)
        self.lng_spin.setValue(DEFAULT_LONGITUDE)
        coord_layout.addWidget(QLabel("Lat:"))
        coord_layout.addWidget(self.lat_spin)
        coord_layout.addWidget(QLabel("Lng:"))
        coord_layout.addWidget(self.lng_spin)
        layout.addRow("Coordinates:", coord_layout)

        self.address_edit = QLineEdit()
        layout.addRow("Address:", self.address_edit)

        self.type_edit = QComboBox()
        self.type_edit.setEditable(True)
        self.type_edit.addItems(["", "Geological", "Geomorphological", "Paleontological",
                                  "Mineralogical", "Structural", "Volcanic", "Other"])
        layout.addRow("Site Type:", self.type_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(100)
        layout.addRow("Description:", self.desc_edit)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

        if site:
            self.name_edit.setText(site.site_name)
            self.lat_spin.setValue(site.latitude)
            self.lng_spin.setValue(site.longitude)
            self.address_edit.setText(site.address or "")
            self.type_edit.setCurrentText(site.site_type or "")
            self.desc_edit.setPlainText(site.site_desc or "")
        elif lat is not None and lng is not None:
            self.lat_spin.setValue(lat)
            self.lng_spin.setValue(lng)

    def _apply_coord_input(self):
        text = self.coord_input.text().strip()
        if not text:
            return
        result = parse_coordinates(text)
        if result:
            self.lat_spin.setValue(result[0])
            self.lng_spin.setValue(result[1])
            self.coord_input.setStyleSheet("")
        else:
            self.coord_input.setStyleSheet("border: 1px solid red;")

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Site name is required.")
            return
        self.accept()

    def get_site_data(self):
        return {
            "site_name": self.name_edit.text().strip(),
            "latitude": self.lat_spin.value(),
            "longitude": self.lng_spin.value(),
            "address": self.address_edit.text().strip() or None,
            "site_type": self.type_edit.currentText().strip() or None,
            "site_desc": self.desc_edit.toPlainText().strip() or None,
        }


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings(COMPANY_NAME, PROGRAM_NAME)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        map_group = QGroupBox("Map Settings")
        map_layout = QFormLayout(map_group)

        self.default_lat = QDoubleSpinBox()
        self.default_lat.setRange(-90.0, 90.0)
        self.default_lat.setDecimals(6)
        self.default_lat.setValue(self.settings.value("map/default_lat", DEFAULT_LATITUDE, type=float))
        map_layout.addRow("Default Latitude:", self.default_lat)

        self.default_lng = QDoubleSpinBox()
        self.default_lng.setRange(-180.0, 180.0)
        self.default_lng.setDecimals(6)
        self.default_lng.setValue(self.settings.value("map/default_lng", DEFAULT_LONGITUDE, type=float))
        map_layout.addRow("Default Longitude:", self.default_lng)

        self.default_zoom = QComboBox()
        for z in range(1, 20):
            self.default_zoom.addItem(str(z), z)
        current_zoom = self.settings.value("map/default_zoom", 10, type=int)
        self.default_zoom.setCurrentText(str(current_zoom))
        map_layout.addRow("Default Zoom:", self.default_zoom)

        layout.addWidget(map_group)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._save_settings)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _save_settings(self):
        self.settings.setValue("map/default_lat", self.default_lat.value())
        self.settings.setValue("map/default_lng", self.default_lng.value())
        self.settings.setValue("map/default_zoom", self.default_zoom.currentData())
        self.accept()


class ReportDialog(QDialog):
    """Dialog for viewing and exporting evaluation reports."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Evaluation Report")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Site Name", "Type", "Road Prox.", "Access.",
            "Vegetation", "Development", "Risk Score", "Risk Level"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        export_csv_btn = QPushButton("Export CSV...")
        export_csv_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_csv_btn)

        export_json_btn = QPushButton("Export JSON...")
        export_json_btn.clicked.connect(self._export_json)
        btn_layout.addWidget(export_json_btn)

        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._load_data()

    def _load_data(self):
        sites = GeoHeritageSite.select().order_by(GeoHeritageSite.site_name)
        self.report_data = []

        for site in sites:
            try:
                ev = (RiskEvaluation
                      .select()
                      .where(RiskEvaluation.site == site)
                      .order_by(RiskEvaluation.evaluated_at.desc())
                      .get())
                row = {
                    "site_name": site.site_name,
                    "site_type": site.site_type or "",
                    "latitude": site.latitude,
                    "longitude": site.longitude,
                    "road_proximity": ev.road_proximity,
                    "accessibility": ev.accessibility,
                    "vegetation_cover": ev.vegetation_cover,
                    "development_signs": ev.development_signs,
                    "overall_risk": ev.overall_risk,
                    "risk_level": ev.risk_level,
                    "evaluator_notes": ev.evaluator_notes or "",
                    "evaluated_at": ev.evaluated_at.isoformat() if ev.evaluated_at else "",
                }
            except RiskEvaluation.DoesNotExist:
                row = {
                    "site_name": site.site_name,
                    "site_type": site.site_type or "",
                    "latitude": site.latitude,
                    "longitude": site.longitude,
                    "road_proximity": "-",
                    "accessibility": "-",
                    "vegetation_cover": "-",
                    "development_signs": "-",
                    "overall_risk": "-",
                    "risk_level": "N/A",
                    "evaluator_notes": "",
                    "evaluated_at": "",
                }
            self.report_data.append(row)

        self.table.setRowCount(len(self.report_data))
        for i, row in enumerate(self.report_data):
            self.table.setItem(i, 0, QTableWidgetItem(str(row["site_name"])))
            self.table.setItem(i, 1, QTableWidgetItem(str(row["site_type"])))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["road_proximity"])))
            self.table.setItem(i, 3, QTableWidgetItem(str(row["accessibility"])))
            self.table.setItem(i, 4, QTableWidgetItem(str(row["vegetation_cover"])))
            self.table.setItem(i, 5, QTableWidgetItem(str(row["development_signs"])))
            self.table.setItem(i, 6, QTableWidgetItem(str(row["overall_risk"])))
            self.table.setItem(i, 7, QTableWidgetItem(str(row["risk_level"])))

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "gheval_report.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.report_data[0].keys() if self.report_data else [])
            writer.writeheader()
            writer.writerows(self.report_data)

        QMessageBox.information(self, "Export", f"Report exported to {path}")

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "gheval_report.json", "JSON Files (*.json)"
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.report_data, f, ensure_ascii=False, indent=2)

        QMessageBox.information(self, "Export", f"Report exported to {path}")


class PdfImportDialog(QDialog):
    """Dialog for extracting and importing coordinates from PDF files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Sites from PDF")
        self.setMinimumSize(850, 550)
        self.setAcceptDrops(True)
        self._pdf_paths = []
        self._worker = None
        self._imported_site_ids = []

        layout = QVBoxLayout(self)

        # ── File selection bar ───────────────────────────
        file_bar = QHBoxLayout()
        add_files_btn = QPushButton("Add Files...")
        add_files_btn.clicked.connect(self._add_files)
        file_bar.addWidget(add_files_btn)

        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self._add_folder)
        file_bar.addWidget(add_folder_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_files)
        file_bar.addWidget(clear_btn)

        file_bar.addStretch()
        self._file_count_label = QLabel("No files selected")
        file_bar.addWidget(self._file_count_label)

        self._process_btn = QPushButton("Process")
        self._process_btn.clicked.connect(self._start_processing)
        self._process_btn.setEnabled(False)
        file_bar.addWidget(self._process_btn)

        layout.addLayout(file_bar)

        # ── File list ────────────────────────────────────
        self._file_list = QListWidget()
        self._file_list.setMaximumHeight(100)
        self._file_list.setAlternatingRowColors(True)
        layout.addWidget(self._file_list)

        # ── Progress bar (hidden until processing) ───────
        self._progress_widget = QWidget()
        progress_layout = QHBoxLayout(self._progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_bar = QProgressBar()
        progress_layout.addWidget(self._progress_bar, 1)
        self._progress_label = QLabel("")
        progress_layout.addWidget(self._progress_label)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._cancel_processing)
        self._cancel_btn = cancel_btn
        progress_layout.addWidget(cancel_btn)
        self._progress_widget.setVisible(False)
        layout.addWidget(self._progress_widget)

        # ── Results table ────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "", "Site Name", "Latitude", "Longitude", "Source PDF", "Page", "Context"
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 200)
        self._table.setColumnWidth(4, 150)
        layout.addWidget(self._table, 1)

        # ── Summary bar ──────────────────────────────────
        summary_bar = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        summary_bar.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._set_all_checked(False))
        summary_bar.addWidget(deselect_all_btn)

        summary_bar.addStretch()
        self._summary_label = QLabel("")
        summary_bar.addWidget(self._summary_label)
        layout.addLayout(summary_bar)

        # ── Bottom buttons ───────────────────────────────
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self._import_btn = QPushButton("Import Selected")
        self._import_btn.clicked.connect(self._import_selected)
        self._import_btn.setEnabled(False)
        bottom_bar.addWidget(self._import_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(close_btn)
        layout.addLayout(bottom_bar)

    # ── Drag & drop ───────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        from GhPdfExtractor import collect_pdf_paths
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)
        if paths:
            self._pdf_paths = collect_pdf_paths(self._pdf_paths + paths)
            self._update_file_count()

    # ── File management ──────────────────────────────────

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if paths:
            from GhPdfExtractor import collect_pdf_paths
            self._pdf_paths = collect_pdf_paths(self._pdf_paths + paths)
            self._update_file_count()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            from GhPdfExtractor import collect_pdf_paths
            self._pdf_paths = collect_pdf_paths(self._pdf_paths + [folder])
            self._update_file_count()

    def _clear_files(self):
        self._pdf_paths = []
        self._table.setRowCount(0)
        self._file_list.clear()
        self._update_file_count()
        self._import_btn.setEnabled(False)
        self._summary_label.setText("")

    def _update_file_count(self):
        n = len(self._pdf_paths)
        self._file_count_label.setText(f"{n} file{'s' if n != 1 else ''} selected")
        self._process_btn.setEnabled(n > 0)
        self._file_list.clear()
        for p in self._pdf_paths:
            self._file_list.addItem(os.path.basename(p))

    # ── Processing ───────────────────────────────────────

    def _start_processing(self):
        if not self._pdf_paths:
            return

        from GhPdfExtractor import PdfProcessorWorker

        self._table.setRowCount(0)
        self._process_btn.setEnabled(False)
        self._import_btn.setEnabled(False)
        self._summary_label.setText("")
        self._progress_widget.setVisible(True)
        self._progress_bar.setMaximum(len(self._pdf_paths))
        self._progress_bar.setValue(0)

        self._worker = PdfProcessorWorker(self._pdf_paths, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_completed.connect(self._on_file_completed)
        self._worker.all_completed.connect(self._on_all_completed)
        self._worker.start()

    def _cancel_processing(self):
        if self._worker:
            self._worker.cancel()

    def _on_progress(self, current, total, filename):
        self._progress_bar.setValue(current)
        self._progress_label.setText(f"Processing {filename}...")

    def _on_file_completed(self, pdf_result):
        for site in pdf_result.sites:
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Checkbox
            cb = QCheckBox()
            cb.setChecked(True)
            self._table.setCellWidget(row, 0, cb)

            # Editable site name
            name_item = QTableWidgetItem(site.site_name)
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 1, name_item)

            # Lat, Lng (read-only)
            lat_item = QTableWidgetItem(f"{site.latitude:.6f}")
            lat_item.setFlags(lat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, lat_item)

            lng_item = QTableWidgetItem(f"{site.longitude:.6f}")
            lng_item.setFlags(lng_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 3, lng_item)

            # Source PDF
            pdf_item = QTableWidgetItem(site.source_pdf)
            pdf_item.setFlags(pdf_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 4, pdf_item)

            # Page
            page_item = QTableWidgetItem(str(site.page_number))
            page_item.setFlags(page_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 5, page_item)

            # Context
            ctx_item = QTableWidgetItem(site.context)
            ctx_item.setFlags(ctx_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            ctx_item.setToolTip(site.context)
            self._table.setItem(row, 6, ctx_item)

        # Show warnings in summary
        if pdf_result.warnings:
            current = self._summary_label.text()
            for w in pdf_result.warnings:
                if current:
                    current += " | "
                current += w
            self._summary_label.setText(current)

    def _on_all_completed(self, batch_result):
        self._progress_widget.setVisible(False)
        self._process_btn.setEnabled(True)
        self._worker = None

        total = batch_result.total_sites
        self._summary_label.setText(
            f"Found {total} site{'s' if total != 1 else ''} "
            f"in {batch_result.successful_count} PDF{'s' if batch_result.successful_count != 1 else ''}"
            f"{f' ({batch_result.failed_count} failed)' if batch_result.failed_count else ''}"
        )
        self._import_btn.setEnabled(total > 0)

    # ── Selection helpers ────────────────────────────────

    def _set_all_checked(self, checked):
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.setChecked(checked)

    # ── Import ───────────────────────────────────────────

    def _import_selected(self):
        self._imported_site_ids = []
        count = 0

        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if not cb or not cb.isChecked():
                continue

            name = self._table.item(row, 1).text().strip()
            lat = float(self._table.item(row, 2).text())
            lng = float(self._table.item(row, 3).text())
            source = self._table.item(row, 4).text()
            context = self._table.item(row, 6).text()

            site = GeoHeritageSite.create(
                site_name=name or f"Imported Site {row + 1}",
                latitude=lat,
                longitude=lng,
                site_desc=f"Extracted from: {source}\n{context}",
                site_type="Paleontological",
            )
            self._imported_site_ids.append(site.id)
            count += 1

        if count:
            QMessageBox.information(
                self, "Import Complete",
                f"Successfully imported {count} site{'s' if count != 1 else ''}."
            )
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "No sites were selected for import.")

    def get_imported_site_ids(self):
        """Return list of created site IDs."""
        return self._imported_site_ids
