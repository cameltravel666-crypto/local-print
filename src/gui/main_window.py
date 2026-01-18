# -*- coding: utf-8 -*-
"""
Seisei Print Agent - Main Window
PyQt6 GUI for the print service

Developed by Seisei
"""

import sys
import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QTextEdit, QGroupBox, QFormLayout, QSpinBox, QCheckBox,
    QComboBox, QMessageBox, QSystemTrayIcon, QMenu, QSplitter,
    QHeaderView, QStatusBar, QToolBar, QDialog, QDialogButtonBox,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QAction, QColor, QTextCursor

from ..core.print_service import PrintService, ServiceState
from ..core.printer_manager import PrinterInfo
from ..utils.config import get_config, ServerConfig

logger = logging.getLogger(__name__)


class ServiceThread(QThread):
    """Background thread for running the print service"""
    state_changed = pyqtSignal(str)
    connection_changed = pyqtSignal(str, bool)
    job_received = pyqtSignal(dict)
    job_completed = pyqtSignal(str, bool, str)
    log_message = pyqtSignal(str, str)

    def __init__(self, service: PrintService):
        super().__init__()
        self.service = service
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Setup service callbacks"""
        self.service.on_state_change(lambda s: self.state_changed.emit(s.value))
        self.service.on_connection_change(lambda sid, c: self.connection_changed.emit(sid, c))
        self.service.on_job_received(lambda d: self.job_received.emit(d))
        self.service.on_job_completed(lambda jid, s, m: self.job_completed.emit(jid, s, m))
        self.service.on_log(lambda l, m: self.log_message.emit(l, m))

    def run(self):
        """Run the service"""
        self.service.start()


class ServerDialog(QDialog):
    """Dialog for adding/editing server configuration"""

    def __init__(self, parent=None, server: Optional[ServerConfig] = None):
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("Add Server" if server is None else "Edit Server")
        self.setMinimumWidth(400)
        self._setup_ui()

        if server:
            self._load_server_data()

    def _setup_ui(self):
        """Setup dialog UI"""
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My Odoo Server")
        layout.addRow("Server Name:", self.name_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://localhost")
        layout.addRow("Server URL:", self.url_edit)

        self.http_port_spin = QSpinBox()
        self.http_port_spin.setRange(1, 65535)
        self.http_port_spin.setValue(8069)
        layout.addRow("HTTP Port:", self.http_port_spin)

        self.ws_port_spin = QSpinBox()
        self.ws_port_spin.setRange(1, 65535)
        self.ws_port_spin.setValue(8072)
        layout.addRow("WebSocket Port:", self.ws_port_spin)

        self.db_edit = QLineEdit()
        self.db_edit.setPlaceholderText("odoo")
        layout.addRow("Database:", self.db_edit)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("admin")
        layout.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Password:", self.password_edit)

        self.auto_connect_check = QCheckBox("Auto connect on startup")
        self.auto_connect_check.setChecked(True)
        layout.addRow("", self.auto_connect_check)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        layout.addRow("", self.enabled_check)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_server_data(self):
        """Load existing server data"""
        if self.server:
            self.name_edit.setText(self.server.server_name)
            self.url_edit.setText(self.server.server_url)
            self.http_port_spin.setValue(self.server.http_port)
            self.ws_port_spin.setValue(self.server.websocket_port)
            self.db_edit.setText(self.server.database)
            self.username_edit.setText(self.server.username)
            self.password_edit.setText(self.server.password)
            self.auto_connect_check.setChecked(self.server.auto_connect)
            self.enabled_check.setChecked(self.server.enabled)

    def get_server_config(self) -> ServerConfig:
        """Get server configuration from dialog"""
        if self.server:
            server_id = self.server.server_id
        else:
            import uuid
            server_id = str(uuid.uuid4())

        return ServerConfig(
            server_id=server_id,
            server_name=self.name_edit.text() or "Unnamed Server",
            server_url=self.url_edit.text() or "http://localhost",
            http_port=self.http_port_spin.value(),
            websocket_port=self.ws_port_spin.value(),
            database=self.db_edit.text() or "odoo",
            username=self.username_edit.text() or "admin",
            password=self.password_edit.text(),
            auto_connect=self.auto_connect_check.isChecked(),
            enabled=self.enabled_check.isChecked(),
        )


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.service: Optional[PrintService] = None
        self.service_thread: Optional[ServiceThread] = None

        self._setup_ui()
        self._setup_tray()
        self._load_config()
        self._init_service()

    def _setup_ui(self):
        """Setup main window UI"""
        self.setWindowTitle("Seisei Print Agent")
        self.setMinimumSize(960, 600)

        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self._create_dashboard_tab()
        self._create_servers_tab()
        self._create_printers_tab()
        self._create_logs_tab()
        self._create_settings_tab()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Toolbar
        self._create_toolbar()

    def _create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        self.start_action = QAction("Start", self)
        self.start_action.triggered.connect(self.start_service)
        toolbar.addAction(self.start_action)

        self.stop_action = QAction("Stop", self)
        self.stop_action.triggered.connect(self.stop_service)
        self.stop_action.setEnabled(False)
        toolbar.addAction(self.stop_action)

        toolbar.addSeparator()

        refresh_action = QAction("Refresh Printers", self)
        refresh_action.triggered.connect(self.refresh_printers)
        toolbar.addAction(refresh_action)

        sync_action = QAction("Sync Now", self)
        sync_action.triggered.connect(self.manual_sync)
        toolbar.addAction(sync_action)

    def _create_dashboard_tab(self):
        """Create dashboard tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Status group
        status_group = QGroupBox("Service Status")
        status_layout = QFormLayout(status_group)

        self.service_status_label = QLabel("Stopped")
        self.service_status_label.setStyleSheet("font-weight: bold; color: red;")
        status_layout.addRow("Status:", self.service_status_label)

        self.connections_label = QLabel("0 / 0")
        status_layout.addRow("Connections:", self.connections_label)

        self.printers_label = QLabel("0")
        status_layout.addRow("Printers:", self.printers_label)

        layout.addWidget(status_group)

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)

        start_btn = QPushButton("Start Service")
        start_btn.clicked.connect(self.start_service)
        actions_layout.addWidget(start_btn)

        stop_btn = QPushButton("Stop Service")
        stop_btn.clicked.connect(self.stop_service)
        actions_layout.addWidget(stop_btn)

        refresh_btn = QPushButton("Refresh Printers")
        refresh_btn.clicked.connect(self.refresh_printers)
        actions_layout.addWidget(refresh_btn)

        layout.addWidget(actions_group)

        # Recent activity
        activity_group = QGroupBox("Recent Activity")
        activity_layout = QVBoxLayout(activity_group)

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(4)
        self.activity_table.setHorizontalHeaderLabels(["Time", "Type", "Printer", "Status"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        activity_layout.addWidget(self.activity_table)

        layout.addWidget(activity_group)

        self.tabs.addTab(widget, "Dashboard")

    def _create_servers_tab(self):
        """Create servers tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Servers table
        self.servers_table = QTableWidget()
        self.servers_table.setColumnCount(5)
        self.servers_table.setHorizontalHeaderLabels(["Name", "URL", "Database", "Status", "Actions"])
        self.servers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.servers_table)

        # Buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add Server")
        add_btn.clicked.connect(self.add_server)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self.edit_server)
        btn_layout.addWidget(edit_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_server)
        btn_layout.addWidget(remove_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(widget, "Servers")

    def _create_printers_tab(self):
        """Create printers tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Printers table
        self.printers_table = QTableWidget()
        self.printers_table.setColumnCount(5)
        self.printers_table.setHorizontalHeaderLabels(["Name", "Model", "Status", "Default", "Actions"])
        self.printers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.printers_table)

        # Buttons
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_printers)
        btn_layout.addWidget(refresh_btn)

        test_btn = QPushButton("Test Print")
        test_btn.clicked.connect(self.test_print)
        btn_layout.addWidget(test_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tabs.addTab(widget, "Printers")

    def _create_logs_tab(self):
        """Create logs tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(self.log_text.font())
        layout.addWidget(self.log_text)

        # Controls
        ctrl_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.log_text.clear)
        ctrl_layout.addWidget(clear_btn)

        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        ctrl_layout.addWidget(self.auto_scroll_check)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.tabs.addTab(widget, "Logs")

    def _create_settings_tab(self):
        """Create settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.machine_name_edit = QLineEdit()
        self.machine_name_edit.setPlaceholderText("My Computer")
        layout.addRow("Machine Name:", self.machine_name_edit)

        self.machine_id_edit = QLineEdit()
        layout.addRow("Machine ID:", self.machine_id_edit)

        self.location_tag_edit = QLineEdit()
        self.location_tag_edit.setPlaceholderText("Office A")
        layout.addRow("Location Tag:", self.location_tag_edit)

        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(10, 300)
        self.sync_interval_spin.setValue(30)
        self.sync_interval_spin.setSuffix(" seconds")
        layout.addRow("Sync Interval:", self.sync_interval_spin)

        self.auto_start_check = QCheckBox("Start service on application launch")
        layout.addRow("", self.auto_start_check)

        self.minimize_tray_check = QCheckBox("Minimize to system tray")
        self.minimize_tray_check.setChecked(True)
        layout.addRow("", self.minimize_tray_check)

        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addRow("", save_btn)

        self.tabs.addTab(widget, "Settings")

    def _setup_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)

        # Tray menu
        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        start_action = QAction("Start Service", self)
        start_action.triggered.connect(self.start_service)
        tray_menu.addAction(start_action)

        stop_action = QAction("Stop Service", self)
        stop_action.triggered.connect(self.stop_service)
        tray_menu.addAction(stop_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    def _load_config(self):
        """Load configuration into UI"""
        # Settings
        self.machine_name_edit.setText(self.config.settings.machine_name)
        self.machine_id_edit.setText(self.config.settings.machine_id)
        self.location_tag_edit.setText(self.config.settings.station_tag)
        self.sync_interval_spin.setValue(self.config.settings.scan_interval)
        self.auto_start_check.setChecked(self.config.settings.auto_start)
        self.minimize_tray_check.setChecked(self.config.settings.minimize_tray)

        # Servers
        self._update_servers_table()

    def _init_service(self):
        """Initialize print service"""
        machine_name = self.config.settings.machine_name or "Seisei Print Agent"
        machine_id = self.config.settings.machine_id
        location_tag = self.config.settings.station_tag

        self.service = PrintService(machine_name, machine_id, location_tag)
        self.service.set_sync_interval(self.config.settings.scan_interval)

        # Add configured servers
        for server_id, server in self.config.servers.items():
            if server.enabled:
                self.service.add_server(
                    server_id=server.server_id,
                    server_name=server.server_name,
                    server_url=server.server_url,
                    database=server.database,
                    username=server.username,
                    password=server.password,
                    http_port=server.http_port,
                    websocket_port=server.websocket_port,
                )

        # Discover printers
        self.refresh_printers()

        # Auto start if configured
        if self.config.settings.auto_start:
            QTimer.singleShot(1000, self.start_service)

    def _update_servers_table(self):
        """Update servers table"""
        self.servers_table.setRowCount(len(self.config.servers))

        for row, (server_id, server) in enumerate(self.config.servers.items()):
            self.servers_table.setItem(row, 0, QTableWidgetItem(server.server_name))
            self.servers_table.setItem(row, 1, QTableWidgetItem(f"{server.server_url}:{server.http_port}"))
            self.servers_table.setItem(row, 2, QTableWidgetItem(server.database))

            status = "Enabled" if server.enabled else "Disabled"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor("green" if server.enabled else "gray"))
            self.servers_table.setItem(row, 3, status_item)

            # Store server_id in first column for reference
            self.servers_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, server_id)

    def _update_printers_table(self):
        """Update printers table"""
        if not self.service:
            return

        printers = self.service.get_printers()
        self.printers_table.setRowCount(len(printers))
        self.printers_label.setText(str(len(printers)))

        for row, printer in enumerate(printers):
            self.printers_table.setItem(row, 0, QTableWidgetItem(printer.name))
            self.printers_table.setItem(row, 1, QTableWidgetItem(printer.model or "-"))
            self.printers_table.setItem(row, 2, QTableWidgetItem(printer.status))
            self.printers_table.setItem(row, 3, QTableWidgetItem("Yes" if printer.is_default else "No"))

    def _add_log(self, level: str, message: str):
        """Add log message to log view"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        color_map = {
            "info": "black",
            "warning": "orange",
            "error": "red",
            "debug": "gray",
        }
        color = color_map.get(level.lower(), "black")

        html = f'<span style="color: {color};">[{timestamp}] [{level.upper()}] {message}</span><br>'
        self.log_text.insertHtml(html)

        if self.auto_scroll_check.isChecked():
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def _add_activity(self, activity_type: str, printer: str, status: str):
        """Add activity to dashboard"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        row = self.activity_table.rowCount()
        self.activity_table.insertRow(0)  # Insert at top
        self.activity_table.setItem(0, 0, QTableWidgetItem(timestamp))
        self.activity_table.setItem(0, 1, QTableWidgetItem(activity_type))
        self.activity_table.setItem(0, 2, QTableWidgetItem(printer))
        self.activity_table.setItem(0, 3, QTableWidgetItem(status))

        # Keep only last 100 entries
        while self.activity_table.rowCount() > 100:
            self.activity_table.removeRow(self.activity_table.rowCount() - 1)

    # ============ Actions ============

    def start_service(self):
        """Start the print service"""
        if not self.service:
            return

        if len(self.config.servers) == 0:
            QMessageBox.warning(self, "No Servers", "Please add at least one server before starting.")
            return

        self.service_thread = ServiceThread(self.service)
        self.service_thread.state_changed.connect(self._on_service_state_changed)
        self.service_thread.connection_changed.connect(self._on_connection_changed)
        self.service_thread.job_received.connect(self._on_job_received)
        self.service_thread.job_completed.connect(self._on_job_completed)
        self.service_thread.log_message.connect(self._add_log)
        self.service_thread.start()

        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)

    def stop_service(self):
        """Stop the print service"""
        if self.service:
            self.service.stop()

        if self.service_thread:
            self.service_thread.wait(5000)
            self.service_thread = None

        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)

    def refresh_printers(self):
        """Refresh printer list"""
        if self.service:
            self.service.refresh_printers()
            self._update_printers_table()
            self._add_log("info", "Printers refreshed")

    def manual_sync(self):
        """Manually sync printers to servers"""
        if self.service:
            self.service.manual_sync()
            self._add_log("info", "Manual sync triggered")

    def add_server(self):
        """Add new server"""
        dialog = ServerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            server = dialog.get_server_config()
            self.config.add_server(server)
            self._update_servers_table()

            if self.service and server.enabled:
                self.service.add_server(
                    server_id=server.server_id,
                    server_name=server.server_name,
                    server_url=server.server_url,
                    database=server.database,
                    username=server.username,
                    password=server.password,
                    http_port=server.http_port,
                    websocket_port=server.websocket_port,
                )

    def edit_server(self):
        """Edit selected server"""
        row = self.servers_table.currentRow()
        if row < 0:
            return

        server_id = self.servers_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        server = self.config.get_server(server_id)
        if not server:
            return

        dialog = ServerDialog(self, server)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_server = dialog.get_server_config()
            self.config.servers[server_id] = new_server
            self.config.save()
            self._update_servers_table()

    def remove_server(self):
        """Remove selected server"""
        row = self.servers_table.currentRow()
        if row < 0:
            return

        server_id = self.servers_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        server = self.config.get_server(server_id)
        if not server:
            return

        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Are you sure you want to remove server '{server.server_name}'?"
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_server(server_id)
            self._update_servers_table()

            if self.service:
                self.service.remove_server(server_id)

    def test_print(self):
        """Test print on selected printer"""
        row = self.printers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Printer Selected", "Please select a printer first.")
            return

        printer_name = self.printers_table.item(row, 0).text()

        if self.service:
            success = self.service.printer_manager.print_test_page(printer_name)
            if success:
                self._add_log("info", f"Test page sent to {printer_name}")
                self._add_activity("Test Print", printer_name, "Sent")
            else:
                self._add_log("error", f"Failed to print test page on {printer_name}")
                self._add_activity("Test Print", printer_name, "Failed")

    def save_settings(self):
        """Save settings"""
        self.config.settings.machine_name = self.machine_name_edit.text()
        self.config.settings.machine_id = self.machine_id_edit.text()
        self.config.settings.station_tag = self.location_tag_edit.text()
        self.config.settings.scan_interval = self.sync_interval_spin.value()
        self.config.settings.auto_start = self.auto_start_check.isChecked()
        self.config.settings.minimize_tray = self.minimize_tray_check.isChecked()
        self.config.save()

        if self.service:
            self.service.machine_name = self.config.settings.machine_name
            self.service.machine_id = self.config.settings.machine_id
            self.service.location_tag = self.config.settings.station_tag
            self.service.set_sync_interval(self.config.settings.scan_interval)

        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")

    # ============ Event Handlers ============

    def _on_service_state_changed(self, state: str):
        """Handle service state change"""
        self.service_status_label.setText(state.capitalize())

        color_map = {
            "stopped": "red",
            "starting": "orange",
            "running": "green",
            "stopping": "orange",
            "error": "red",
        }
        color = color_map.get(state, "black")
        self.service_status_label.setStyleSheet(f"font-weight: bold; color: {color};")

        self.status_label.setText(f"Service: {state}")

    def _on_connection_changed(self, server_id: str, connected: bool):
        """Handle connection change"""
        # Update servers table status
        for row in range(self.servers_table.rowCount()):
            item = self.servers_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == server_id:
                status = "Connected" if connected else "Disconnected"
                status_item = QTableWidgetItem(status)
                status_item.setForeground(QColor("green" if connected else "red"))
                self.servers_table.setItem(row, 3, status_item)
                break

        # Update connections count
        if self.service:
            connections = self.service.get_connections()
            connected_count = sum(1 for c in connections if c['is_connected'])
            self.connections_label.setText(f"{connected_count} / {len(connections)}")

    def _on_job_received(self, data: dict):
        """Handle job received"""
        printer = data.get('printer_name', 'Unknown')
        self._add_activity("Print Job", printer, "Received")

    def _on_job_completed(self, job_id: str, success: bool, message: str):
        """Handle job completed"""
        status = "Completed" if success else "Failed"
        self._add_activity("Print Job", job_id[:8], status)

    # ============ Window Events ============

    def closeEvent(self, event):
        """Handle window close"""
        if self.config.settings.minimize_tray:
            event.ignore()
            self.hide()
        else:
            self.quit_app()

    def quit_app(self):
        """Quit the application"""
        self.stop_service()
        self.tray_icon.hide()
        QApplication.quit()
