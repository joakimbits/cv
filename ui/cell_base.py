# file: ui/cell_base.py
from __future__ import annotations
from typing import Protocol
from PySide6 import QtCore, QtWidgets

class CellProtocol(Protocol):
    """
    Minimal contract any 'cell' widget must satisfy to plug into list editors.

    Signals (Qt, using 'object' payloads for generality):
      - splitRequested(sender: QObject, head: object, tail: object)
      - emptyBlurred(sender: QObject)

    API:
      - natural_px(col_w: int) -> int : height in pixels (integral line multiples)
    """
    splitRequested: QtCore.SignalInstance  # (object sender, object head, object tail)
    emptyBlurred: QtCore.SignalInstance    # (object sender)

    def natural_px(self, col_w: int) -> int: ...
    def setFocus(self, reason: QtCore.Qt.FocusReason) -> None: ...
    def clearFocus(self) -> None: ...
    def update(self) -> None: ...

# Optional helper for type checkers
def is_cell(w: QtWidgets.QWidget) -> bool:
    return all(
        hasattr(w, name) for name in ("splitRequested", "emptyBlurred", "natural_px")
    )
