# ui/elide.py
from PySide6 import QtCore, QtGui, QtWidgets

class _LineElide(QtCore.QObject):
    def __init__(self, le: QtWidgets.QLineEdit, *, auto=True):
        super().__init__(le)
        self.le = le
        self.auto = auto
        le.installEventFilter(self)
        le.textChanged.connect(le.update)
        le.cursorPositionChanged.connect(le.update)
        le.selectionChanged.connect(le.update)

    def _mode(self) -> QtCore.Qt.TextElideMode:
        if self.auto and "://" in self.le.text():
            return QtCore.Qt.ElideMiddle
        return QtCore.Qt.ElideRight

    def _paint(self):
        p = QtGui.QPainter(self.le)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        p.fillRect(self.le.rect(), self.le.palette().brush(QtGui.QPalette.Base))
        r = self.le.contentsRect().adjusted(2, 0, -2, 0)
        fm = self.le.fontMetrics()
        txt = fm.elidedText(self.le.text(), self._mode(), max(1, r.width()))
        p.setPen(self.le.palette().color(QtGui.QPalette.Text))
        p.drawText(r, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, txt)

    def eventFilter(self, obj, ev):
        if obj is self.le:
            t = ev.type()
            if t in (QtCore.QEvent.FocusIn, QtCore.QEvent.FocusOut, QtCore.QEvent.Resize):
                self.le.update()
            if t == QtCore.QEvent.Paint and self.le.echoMode() == QtWidgets.QLineEdit.Normal and not self.le.hasFocus():
                self._paint()
                return True
        return False

def attach_line_elide(le: QtWidgets.QLineEdit) -> _LineElide:
    return _LineElide(le, auto=True)
