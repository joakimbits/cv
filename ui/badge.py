# ui/badge.py
from PySide6 import QtCore, QtGui, QtWidgets

def count_wrapped_lines(doc: QtGui.QTextDocument) -> int:
    n = 0; b = doc.firstBlock()
    while b.isValid():
        lay = b.layout() or (doc.documentLayout().update() or b.layout())
        n += max(1, (lay.lineCount() if lay else 1))
        b = b.next()
    return max(1, n)

class OverflowBadge(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "…"
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    def set_text(self, t: str):
        if t != self._text:
            self._text = t; self.update()

    def sizeHint(self):
        fm = QtGui.QFontMetrics(self.font())
        return QtCore.QSize(fm.horizontalAdvance(self._text) + 12, fm.height() + 4)

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(self.palette().color(QtGui.QPalette.Mid))
        p.setBrush(self.palette().color(QtGui.QPalette.Midlight))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(self.palette().color(QtGui.QPalette.WindowText))
        p.drawText(self.rect().adjusted(6, 2, -6, -2), QtCore.Qt.AlignCenter, self._text)

class OverflowBadgeCtl(QtCore.QObject):
    def __init__(self, edit: QtWidgets.QTextEdit, *, max_lines: int):
        super().__init__(edit)
        self.edit, self.max_lines = edit, int(max_lines)
        self.badge = OverflowBadge(edit); self.badge.hide()
        edit.installEventFilter(self)
        edit.document().documentLayout().documentSizeChanged.connect(self.refresh)
        QtCore.QTimer.singleShot(0, self.refresh)

    @QtCore.Slot()
    def refresh(self):
        wrapped = count_wrapped_lines(self.edit.document())
        extra = max(0, wrapped - self.max_lines)
        if extra <= 0:
            self.badge.hide(); return
        self.badge.set_text(f"… {extra} more")
        sz = self.badge.sizeHint(); cr = self.edit.contentsRect()
        self.badge.setGeometry(cr.right()-sz.width()-2, cr.bottom()-sz.height()-2, sz.width(), sz.height())
        self.badge.show()

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            self.refresh()
        return False
