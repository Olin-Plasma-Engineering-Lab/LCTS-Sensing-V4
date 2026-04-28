"""Editable step tables used by Timed and CSV modes.

Two flavors:

* `AngleStepTable` stores `(angle: int, duration: float)` rows. Used by
  CSV import — direction keywords in the source CSV are resolved to
  integer angles at parse time.

* `DirectionStepTable` stores `(direction: "up" | "down" | "zero",
  duration: float)` rows. Used by the Timed sequence tab so users pick
  intent rather than a numerical angle. Resolution to an actual angle
  happens at run time using whatever the current up/zero/down values
  are in the configuration UI.

Also exposes `parse_steps_csv`, which reads (angle, duration) pairs
from a CSV file.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .constants import DEFAULT_POSITION_DOWN, DEFAULT_POSITION_UP, DEFAULT_POSITION_ZERO


# Direction keywords. Order in the dropdown matches the typical user mental model:
# move out, return to neutral, move back.
_DIRECTIONS = ("up", "zero", "down")


class _StepTableBase(QWidget):
    """Common scaffolding: table + Add / Remove / Clear button row.

    Subclasses define column count, headers, and per-row creation/reading.
    """

    _columns: Tuple[str, ...] = ()  # set by subclass

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, len(self._columns))
        self._table.setHorizontalHeaderLabels(list(self._columns))
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add row")
        self._btn_remove = QPushButton("Remove selected")
        self._btn_clear = QPushButton("Clear")
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self.add_row)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_clear.clicked.connect(self.clear)

    # Hook for subclasses
    def add_row(self) -> None:
        raise NotImplementedError

    def _remove_selected(self) -> None:
        rows = sorted({i.row() for i in self._table.selectedIndexes()}, reverse=True)
        for r in rows:
            self._table.removeRow(r)

    def clear(self) -> None:
        self._table.setRowCount(0)


# ----------------------------------------------------------------------
# Angle-based table (CSV import)
# ----------------------------------------------------------------------
class AngleStepTable(_StepTableBase):
    """Two-column editable table: angle (int), duration (seconds)."""

    _columns = ("Angle", "Duration (s)")

    def add_row(self, angle: int = DEFAULT_POSITION_ZERO, duration: float = 1.0) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(str(int(angle))))
        self._table.setItem(row, 1, QTableWidgetItem(f"{duration:g}"))

    def load_steps(self, steps: List[Tuple[int, float]]) -> None:
        self.clear()
        for angle, duration in steps:
            self.add_row(angle, duration)

    def steps(self) -> List[Tuple[int, float]]:
        out: List[Tuple[int, float]] = []
        for r in range(self._table.rowCount()):
            try:
                angle = int(self._table.item(r, 0).text())
                duration = float(self._table.item(r, 1).text())
            except (AttributeError, ValueError):
                continue
            if duration < 0:
                continue
            out.append((angle, duration))
        return out


# ----------------------------------------------------------------------
# Direction-based table (Timed sequence)
# ----------------------------------------------------------------------
class DirectionStepTable(_StepTableBase):
    """Two-column table: direction (dropdown of up/zero/down), duration.

    `steps()` returns `(direction_str, duration)` tuples. The caller is
    responsible for resolving each direction to an integer angle at run
    time using the current up/zero/down configuration values.
    """

    _columns = ("Direction", "Duration (s)")

    def add_row(self, direction: str = "zero", duration: float = 1.0) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        # Column 0: combo box of directions. Setting the combo as the cell
        # widget means clicks open the dropdown directly, no double-click
        # to enter edit mode required.
        cmb = QComboBox()
        cmb.addItems(_DIRECTIONS)
        if direction in _DIRECTIONS:
            cmb.setCurrentText(direction)
        self._table.setCellWidget(row, 0, cmb)
        # Column 1: editable duration text.
        self._table.setItem(row, 1, QTableWidgetItem(f"{duration:g}"))

    def load_steps(self, steps: List[Tuple[str, float]]) -> None:
        self.clear()
        for direction, duration in steps:
            self.add_row(direction, duration)

    def steps(self) -> List[Tuple[str, float]]:
        out: List[Tuple[str, float]] = []
        for r in range(self._table.rowCount()):
            cmb = self._table.cellWidget(r, 0)
            if cmb is None:
                continue
            direction = cmb.currentText().lower()
            if direction not in _DIRECTIONS:
                continue
            try:
                duration = float(self._table.item(r, 1).text())
            except (AttributeError, ValueError):
                continue
            if duration < 0:
                continue
            out.append((direction, duration))
        return out


# ----------------------------------------------------------------------
# CSV parser
# ----------------------------------------------------------------------
def parse_steps_csv(
    path: str,
    *,
    up_angle: int = DEFAULT_POSITION_UP,
    down_angle: int = DEFAULT_POSITION_DOWN,
    zero_angle: int = DEFAULT_POSITION_ZERO,
) -> List[Tuple[int, float]]:
    """Read (angle, duration) pairs from a step CSV.

    Each non-blank, non-comment line must have at least two comma-separated
    fields. The first is either an integer angle or one of ``up`` / ``u`` /
    ``down`` / ``d`` / ``zero``. The second is the duration in seconds.
    Negative durations and unparseable rows are silently skipped.
    """
    out: List[Tuple[int, float]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            parts = [p.strip() for p in s.split(",")]
            if len(parts) < 2:
                continue
            a_part, d_part = parts[0], parts[1]
            try:
                duration = float(d_part)
            except ValueError:
                continue
            if duration < 0:
                continue
            try:
                angle = int(a_part)
            except ValueError:
                a = a_part.lower()
                if a in ("up", "u"):
                    angle = up_angle
                elif a in ("down", "d"):
                    angle = down_angle
                else:
                    angle = zero_angle
            out.append((angle, duration))
    return out


# Back-compat alias so existing imports of `StepTable` keep working.
StepTable = AngleStepTable
