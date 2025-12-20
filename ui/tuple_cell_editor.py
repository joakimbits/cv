# file: ui/tuple_cell_editor.py
from __future__ import annotations
import math
from typing import Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
from ui.cell_base import CellProtocol

Tuple2 = Tuple[str, str]

class Tuple2Cell(QtWidgets.QWidget):
    """
    Two-field tuple cell (Tuple[str, str]) with the SAME signals as string cells:
      - splitRequested(sender, head: Tuple[str,str], tail: Tuple[str,str])
      - emptyBlurred(sender)  (fires when BOTH fields are empty)
    Enter splits the **active field**; the other field is duplicated into both head and tail
    (simple, predictable default; easy to change later).
    """
    splitRequested = QtCore.Signal(object, object, object)
    emptyBlurred = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.left = QtWidgets.QLineEdit(self)
        self.right = QtWidgets.QLineEdit(self)
        for le in (self.left, self.right):
            le.setFrame(False)
            le.installEventFilter(self)
        lay.addWidget(self.left, 1)
        lay.addWidget(self.right, 1)

        self.left.editingFinished.connect(self._on_blur)
        self.right.editingFinished.connect(self._on_blur)

    # ---- API for list editors ----
    def setTuple(self, t: Tuple2) -> None:
        blkL = self.left.blockSignals(True); blkR = self.right.blockSignals(True)
        self.left.setText(t[0]); self.right.setText(t[1])
        self.left.blockSignals(blkL); self.right.blockSignals(blkR)

    def getTuple(self) -> Tuple2:
        return (self.left.text(), self.right.text())

    def natural_px(self, col_w: int) -> int:
        fm = QtGui.QFontMetricsF(self.font())
        lh = fm.lineSpacing() or 1.0
        m = self.contentsMargins()
        border = m.top() + m.bottom()
        return int(math.ceil(lh + border))

    # ---- event handling ----
    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if ev.type() == QtCore.QEvent.KeyPress:
            e = QtGui.QKeyEvent(ev)
            if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                t = self.getTuple()
                if obj is self.left:
                    pos = self.left.cursorPosition()
                    head = (t[0][:pos], t[1])
                    tail = (t[0][pos:], t[1])
                else:
                    pos = self.right.cursorPosition()
                    head = (t[0], t[1][:pos])
                    tail = (t[0], t[1][pos:])
                self.splitRequested.emit(self, head, tail)
                e.accept()
                return True
        return super().eventFilter(obj, ev)

    @QtCore.Slot()
    def _on_blur(self) -> None:
        if not self.left.text() and not self.right.text():
            self.emptyBlurred.emit(self)
