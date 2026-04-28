"""calibrate_py.gui — PySide6 GUI for the LabJack T7 calibration system.

Public API:

    from calibrate_py.gui import main, CalibrateMainWindow

The submodules (live_plot_widget, step_table, main_window, constants)
are intentionally not imported eagerly to keep `import calibrate_py.gui`
cheap when something else in the package just needs e.g. a constant.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the GUI. Returns the Qt exit code."""
    from PySide6.QtWidgets import QApplication
    from .main_window import CalibrateMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = CalibrateMainWindow()
    win.show()
    return app.exec()


# Convenience re-export so callers can do `from calibrate_py.gui import CalibrateMainWindow`.
def __getattr__(name: str):
    if name == "CalibrateMainWindow":
        from .main_window import CalibrateMainWindow
        return CalibrateMainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    sys.exit(main())
