# file: ui/cells_str.py
from __future__ import annotations
import math
from PySide6 import QtCore, QtGui, QtWidgets

class ElidedLineEdit(QtWidgets.QLineEdit):
    """One-line cell with split + delete signals. Elision is added via elide.attach_line_elide()."""
    splitRequested = QtCore.Signal(object, str, str)
    emptyBlurred = QtCore.Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrame(False)
    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            pos = self.cursorPosition(); t = self.text()
            self.splitRequested.emit(self, t[:pos], t[pos:]); e.accept(); return
        super().keyPressEvent(e)
    def focusOutEvent(self, e: QtGui.QFocusEvent) -> None:
        super().focusOutEvent(e); self.update()
        if not self.text(): self.emptyBlurred.emit(self)
    def insertFromMimeData(self, src: QtGui.QMimeData) -> None:
        if src.hasText():
            s = src.text()  # let Qt decide; no normalization
            if "\n" in s:  # real multiline paste -> split cells
                pos = self.cursorPosition()
                cur = self.text()
                parts = s.split("\n")  # keep trailing empty
                head = cur[:pos] + parts[0]
                tail = "\n".join(parts[1:] + [cur[pos:]])
                self.splitRequested.emit(self, head, tail)
                return
        super().insertFromMimeData(src)
    def natural_px(self, col_w: int) -> int:
        fm = QtGui.QFontMetricsF(self.font()); lh = fm.lineSpacing() or 1.0
        m = self.contentsMargins(); return int((lh + m.top() + m.bottom()) + 0.9999)

class CellTextEdit(QtWidgets.QTextEdit):
    """Wrapped cell with split + delete signals; integral line heights up to max_lines."""
    splitRequested = QtCore.Signal(object, str, str)
    emptyBlurred = QtCore.Signal(object)
    def __init__(self, parent=None, *, min_lines: int = 1, max_lines: int = 6):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self._min_lines = max(1, int(min_lines))
        self._max_lines = max(self._min_lines, int(max_lines))
        self.document().setDocumentMargin(0)
        self.document().setDefaultFont(self.font())  # keep doc metrics aligned with widget font
    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            c = self.textCursor(); t = self.toPlainText()
            self.splitRequested.emit(self, t[:c.position()], t[c.position():]); e.accept(); return
        super().keyPressEvent(e)

    def insertFromMimeData(self, src: QtGui.QMimeData) -> None:
        if src.hasText():
            s = src.text()  # let Qt decide; no normalization
            if "\n" in s:  # real multiline paste -> split cells
                c = self.textCursor()
                cur = self.toPlainText()
                head0, tail0 = cur[:c.position()], cur[c.position():]
                parts = s.split("\n")  # keep trailing empty
                new_head = head0 + parts[0]
                new_tail = "\n".join(parts[1:] + [tail0])
                self.splitRequested.emit(self, new_head, new_tail)
                return
        super().insertFromMimeData(src)
    def focusOutEvent(self, e: QtGui.QFocusEvent) -> None:
        super().focusOutEvent(e); self.viewport().update()
        if not self.toPlainText(): self.emptyBlurred.emit(self)

    def natural_px(self, col_w: int) -> int:
        from ui.badge import count_wrapped_lines  # reuse the exact counter you already have

        doc = self.document()
        text_w = float(max(1, int(col_w)))
        if doc.textWidth() != text_w:
            doc.setTextWidth(text_w)
            # ensure layout is up to date before measuring
            if doc.documentLayout() is not None:
                doc.adjustSize()  # <- triggers (re)layout
                _ = doc.documentLayout().documentSize()  # ensures layout is realized

        # exact wrapped line count (no phantom line)
        wrapped = max(1, count_wrapped_lines(doc))
        # actual laid-out height in pixels (Qt's own computation)
        layout_h = float(doc.documentLayout().documentSize().height())
        per_line = layout_h / wrapped  # matches how the document actually renders

        # clamp to min/max lines
        lines = max(self._min_lines, min(wrapped, self._max_lines))

        m = self.contentsMargins()
        border = m.top() + m.bottom() + self.frameWidth() * 2  # 0 with NoFrame
        return int(math.ceil(lines * per_line + border))

def make_cell(parent: QtWidgets.QWidget, *, max_lines: int, text: str) -> QtWidgets.QWidget:
    if int(max_lines) == 1:
        w = ElidedLineEdit(parent); w.setText(text)
    else:
        w = CellTextEdit(parent, min_lines=1, max_lines=int(max_lines)); w.setPlainText(text)
    return w
