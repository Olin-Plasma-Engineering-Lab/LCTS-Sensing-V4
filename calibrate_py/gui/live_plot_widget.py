"""Embedded live-plot widget: matplotlib canvas inside a QWidget.

Top axis shows the position pin (raw volts). Bottom axis shows
thermocouples as solid colored lines and the cold-junction temperature
as a dashed grey line. Persistent Line2D objects are reused across
updates so we're not recreating artists at the sample rate.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import QVBoxLayout, QWidget


class LivePlotWidget(QWidget):
    """Two-axis matplotlib canvas embedded in a Qt widget."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # constrained_layout reserves space for axis labels, titles, and
        # legends more reliably than tight_layout when the canvas height
        # is small. Without this the bottom xlabel can get clipped.
        self._fig = Figure(figsize=(10, 7), constrained_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax_pos = self._fig.add_subplot(2, 1, 1)
        self._ax_therm = self._fig.add_subplot(2, 1, 2, sharex=self._ax_pos)

        layout = QVBoxLayout(self)
        # Bottom margin keeps the xlabel clear of any widget below.
        layout.setContentsMargins(0, 0, 0, 4)
        layout.addWidget(self._canvas)

        # The plot owns its own tab now, so we don't need an aggressive
        # floor. 200 px keeps it readable on small screens.
        self.setMinimumHeight(200)

        # Persistent line objects so we don't recreate Line2D on every redraw.
        self._line_pos = None
        self._lines_therm: dict = {}
        self._line_cjc = None
        self._pin_names: List[str] = []
        self._show_cjc = False

        self._configure_axes()

    # ------------------------------------------------------------------
    def _configure_axes(self) -> None:
        self._ax_pos.set_ylabel("Position [V]")
        self._ax_therm.set_ylabel("Temperature [C]")
        self._ax_therm.set_xlabel("sample index")
        self._ax_pos.grid(True, alpha=0.3)
        self._ax_therm.grid(True, alpha=0.3)

    def configure_channels(self, pin_names: List[str], show_cjc: bool) -> None:
        """Reset the plot to display the given input pins (and optional CJC).

        Call once per connect; channels don't change mid-capture.
        """
        self._ax_pos.clear()
        self._ax_therm.clear()
        self._line_pos = None
        self._lines_therm.clear()
        self._line_cjc = None
        self._pin_names = list(pin_names)
        self._show_cjc = show_cjc

        if not pin_names:
            self._configure_axes()
            self._canvas.draw_idle()
            return

        # First pin = position (raw V) on top axis.
        pos_pin = pin_names[0]
        (self._line_pos,) = self._ax_pos.plot([], [], color="tab:blue", label=pos_pin)
        self._ax_pos.set_ylabel(f"{pos_pin} [V]")
        self._ax_pos.legend(loc="upper right")

        # Remaining pins = thermocouples on bottom axis.
        for pin in pin_names[1:]:
            (line,) = self._ax_therm.plot([], [], label=pin)
            self._lines_therm[pin] = line

        if show_cjc:
            (self._line_cjc,) = self._ax_therm.plot(
                [], [], color="tab:gray", linestyle="--", linewidth=1.0, label="CJC"
            )

        if pin_names[1:] or show_cjc:
            self._ax_therm.set_ylabel("Temperature [C]")
            self._ax_therm.legend(loc="upper right")

        self._ax_pos.grid(True, alpha=0.3)
        self._ax_therm.grid(True, alpha=0.3)
        self._ax_therm.set_xlabel("sample index")
        self._canvas.draw_idle()

    def update_data(
        self,
        x: np.ndarray,
        pos_data: np.ndarray,
        therm_data: dict,
        cjc_data: Optional[np.ndarray],
    ) -> None:
        """Update existing line data and rescale axes. Cheap; safe at 20 Hz."""
        if self._line_pos is None:
            return
        self._line_pos.set_data(x, pos_data)
        for pin, arr in therm_data.items():
            line = self._lines_therm.get(pin)
            if line is not None:
                line.set_data(x, arr)
        if self._line_cjc is not None and cjc_data is not None:
            self._line_cjc.set_data(x, cjc_data)

        self._ax_pos.relim()
        self._ax_pos.autoscale_view()
        self._ax_therm.relim()
        self._ax_therm.autoscale_view()
        self._canvas.draw_idle()
