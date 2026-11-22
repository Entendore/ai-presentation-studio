#!/usr/bin/env python
"""AI Presentation Studio — Ultimate Edition. Entry point."""
import sys
import atexit
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui import MainWindow
from engine import shutdown_threading, AsyncBridge, AutoSaveManager

def cleanup():
    try:
        AutoSaveManager.instance().shutdown()
        shutdown_threading()
    except Exception as e:
        print(f"Cleanup error: {e}")

def main():
    atexit.register(cleanup)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("AI Presentation Studio")
    app.setOrganizationName("VideoGen")
    app.setStyle("Fusion")
    
    AsyncBridge.instance().start()
    AutoSaveManager.instance().start()
    
    window = MainWindow()
    window.show()
    
    try:
        exit_code = app.exec()
    finally:
        cleanup()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
