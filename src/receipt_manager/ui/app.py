"""
Main window. Shows the HTML pages in ui/web/ inside a QWebEngineView
and exposes the Bridge (ui/bridge.py) to them as `bridge`.

Usage:
    python -m receipt_manager.ui.app
"""

import json
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from receipt_manager.data.migrate import upgrade
from receipt_manager.ui.bridge import Bridge, load_settings

WEB_DIR = Path(__file__).parent / "web"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Receipt Manager")
        self.resize(1280, 800)

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        self.bridge = Bridge()
        self.channel = QWebChannel(self)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # common.js reads window.__SETTINGS__ before the page paints,
        # so the theme is right without waiting for the channel
        self._settings_script = QWebEngineScript()
        self._settings_script.setName("settings")
        self._settings_script.setInjectionPoint(QWebEngineScript.DocumentCreation)
        self._settings_script.setWorldId(QWebEngineScript.MainWorld)
        self._inject_settings(json.dumps(load_settings()))
        self.bridge.settingsChanged.connect(self._inject_settings)

        self.view.load(QUrl.fromLocalFile(str(WEB_DIR / "home.html")))

    def _inject_settings(self, settings_json: str) -> None:
        scripts = self.view.page().scripts()
        scripts.remove(self._settings_script)
        self._settings_script.setSourceCode(f"window.__SETTINGS__ = {settings_json};")
        scripts.insert(self._settings_script)


def main() -> int:
    upgrade()  # make sure the database exists and is on the latest schema
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
