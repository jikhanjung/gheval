import os
import json
import csv
import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDoubleSpinBox, QComboBox, QPushButton, QLabel,
    QDialogButtonBox, QMessageBox, QGroupBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
)
from PyQt6.QtCore import Qt, QSettings

from GhCommons import (
    COMPANY_NAME, PROGRAM_NAME, DEFAULT_LATITUDE, DEFAULT_LONGITUDE,
    calculate_risk_score, get_risk_level,
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
