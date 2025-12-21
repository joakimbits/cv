# file: ui/cell_protocol.py
from __future__ import annotations
from typing import Protocol
from PySide6 import QtCore, QtWidgets

class CellProtocol(Protocol):
    """Any pluggable 'cell' must expose these to editors."""
    splitRequested: QtCore.SignalInstance  # (sender: QObject, head: object, tail: object)
    emptyBlurred: QtCore.SignalInstance    # (sender: QObject)
    def natural_px(self, col_w: int) -> int: ...
    def setFocus(self, reason: QtCore.Qt.FocusReason) -> None: ...
    def clearFocus(self) -> None: ...
    def update(self) -> None: ...

def is_cell(w: QtWidgets.QWidget) -> bool:
    return all(hasattr(w, n) for n in ("splitRequested", "emptyBlurred", "natural_px"))
