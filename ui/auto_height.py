# ui/auto_height.py
from PySide6 import QtCore, QtWidgets

class HeightSizer(QtCore.QObject):
    def __init__(self, host: QtWidgets.QWidget, w: QtWidgets.QWidget):
        super().__init__(host)
        self.host, self.w = host, w
        host.installEventFilter(self)
        w.installEventFilter(self)
        if hasattr(w, "viewport") and callable(w.viewport):
            w.viewport().installEventFilter(self)
        if hasattr(w, "document"):
            try:
                w.document().documentLayout().documentSizeChanged.connect(self.sync)  # type: ignore[attr-defined]
            except Exception:
                pass
        QtCore.QTimer.singleShot(0, self.sync)

    @QtCore.Slot()
    def sync(self, *_):
        width = int(self.host.width() or self.w.width() or 0)
        if width < 10:
            QtCore.QTimer.singleShot(0, self.sync); return
        h = int(self.w.natural_px(width)) if hasattr(self.w, "natural_px") else self.w.sizeHint().height()
        self.w.setMinimumHeight(h)
        self.w.setMaximumHeight(h)

    def eventFilter(self, obj, ev):
        if ev.type() in (QtCore.QEvent.Show, QtCore.QEvent.Resize):
            self.sync()
        return False
