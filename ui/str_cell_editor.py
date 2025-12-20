# file: ui/str_cell_editor.py
from __future__ import annotations

import math
from typing import Optional

from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor
from PySide6 import QtCore, QtGui, QtWidgets

from ui.cell_base import CellProtocol

# ---------- shared badge ----------

class _OverflowBadge(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._text = "…"
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        fm = QtGui.QFontMetrics(self.font())
        return QtCore.QSize(fm.horizontalAdvance(self._text) + 12, fm.height() + 4)

    def paintEvent(self, _: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(self.palette().color(QtGui.QPalette.Mid))
        p.setBrush(self.palette().color(QtGui.QPalette.Midlight))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(self.palette().color(QtGui.QPalette.WindowText))
        p.drawText(self.rect().adjusted(6, 2, -6, -2), QtCore.Qt.AlignCenter, self._text)

# ---------- string cells ----------

class CellTextEdit(QtWidgets.QTextEdit):  # multiline string cell
    splitRequested = QtCore.Signal(object, object, object)  # sender, head:str, tail:str
    emptyBlurred = QtCore.Signal(object)                    # sender

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
        self._badge = _OverflowBadge(self)
        self._badge.hide()
        self.document().setDocumentMargin(0)  # precise line-multiple sizing
        self.document().documentLayout().documentSizeChanged.connect(self._refresh_overflow_badge)

    # events
    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:  # noqa: N802
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            c = self.textCursor()
            t = self.toPlainText()
            self.splitRequested.emit(self, t[:c.position()], t[c.position():])
            e.accept()
            return
        super().keyPressEvent(e)

    def insertFromMimeData(self, source: QtGui.QMimeData) -> None:  # noqa: N802
        if source.hasText():
            s = source.text()
            if "\n" in s:
                c = self.textCursor()
                cur = self.toPlainText()
                head, tail0 = cur[:c.position()], cur[c.position():]
                parts = s.split("\n")  # keep trailing empty
                new_head = head + parts[0]
                new_tails = parts[1:] + [tail0]
                self.splitRequested.emit(self, new_head, "\n".join(new_tails))
                return
        super().insertFromMimeData(source)

    def focusOutEvent(self, e: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(e)
        self.viewport().update()
        if not self.toPlainText():
            self.emptyBlurred.emit(self)

    # sizing
    def natural_px(self, col_w: int) -> int:
        doc = self.document()
        doc.setTextWidth(float(max(1, int(col_w))))
        fm = QtGui.QFontMetricsF(self.font())
        lh = fm.lineSpacing() or 1.0
        doc_h = float(doc.size().height())
        wrapped = max(1, int(math.ceil(doc_h / lh)))
        lines = max(self._min_lines, min(wrapped, self._max_lines))
        m = self.contentsMargins()
        border = m.top() + m.bottom() + self.frameWidth() * 2  # 0 with NoFrame
        return int(math.ceil(lines * lh + border))

    def _refresh_overflow_badge(self) -> None:
        fm = QtGui.QFontMetricsF(self.font())
        lh = fm.lineSpacing() or 1.0
        wrapped = max(1, int(math.ceil(float(self.document().size().height()) / lh)))
        extra = max(0, wrapped - self._max_lines)
        if extra <= 0:
            self._badge.hide()
            return
        self._badge.set_text(f"… {extra} more")
        sz = self._badge.sizeHint()
        cr = self.contentsRect()
        self._badge.setGeometry(cr.right() - sz.width() - 2, cr.bottom() - sz.height() - 2, sz.width(), sz.height())
        self._badge.show()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._refresh_overflow_badge()


class ElidedLineEdit(QtWidgets.QLineEdit):  # one-line string cell
    splitRequested = QtCore.Signal(object, object, object)  # sender, head:str, tail:str
    emptyBlurred = QtCore.Signal(object)                    # sender

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrame(False)

    # events
    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:  # noqa: N802
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            pos = self.cursorPosition()
            t = self.text()
            self.splitRequested.emit(self, t[:pos], t[pos:])
            e.accept()
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(e)
        self.update()
        if not self.text():
            self.emptyBlurred.emit(self)

    # sizing
    def natural_px(self, col_w: int) -> int:
        fm = QtGui.QFontMetricsF(self.font())
        lh = fm.lineSpacing() or 1.0
        m = self.contentsMargins()
        border = m.top() + m.bottom()
        return int(math.ceil(lh + border))

    # paint (elide URL or long text when unfocused)
    def paintEvent(self, e: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self.hasFocus():
            return super().paintEvent(e)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        p.fillRect(self.rect(), self.palette().brush(QtGui.QPalette.Base))
        fm = QtGui.QFontMetrics(self.font())
        avail = max(1, self.contentsRect().width() - 4)
        mode = QtCore.Qt.ElideMiddle if "://" in self.text() else QtCore.Qt.ElideRight
        elided = fm.elidedText(self.text(), mode, avail)
        r = self.contentsRect().adjusted(2, 0, -2, 0)
        p.setPen(self.palette().color(QtGui.QPalette.Text))
        p.drawText(r, int(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft), elided)

# ---------- factory + Traits single-item editor ----------

def make_cell(parent: QtWidgets.QWidget, *, max_lines: int, text: str) -> CellProtocol:
    if int(max_lines) == 1:
        w = ElidedLineEdit(parent)
        w.setText(text)
    else:
        w = CellTextEdit(parent, min_lines=1, max_lines=int(max_lines))
        w.setPlainText(text)
    return w  # conforms to CellProtocol

class _FlowStrEditor(Editor):
    """Standalone Item(Str) editor using the same cells."""
    def init(self, parent):
        host = QtWidgets.QWidget(parent if isinstance(parent, QtWidgets.QWidget) else None)
        layout = QtWidgets.QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._cell = make_cell(host, max_lines=int(self.factory.max_lines), text=self.value or "")
        layout.addWidget(self._cell)
        self.control = host

        # Wire text to Traits value
        if isinstance(self._cell, ElidedLineEdit):
            self._cell.textEdited.connect(self._on_text)
            self._cell.emptyBlurred.connect(lambda *_: None)
            self._cell.splitRequested.connect(self._on_split)
        else:
            self._cell.textChanged.connect(self._on_text)
            self._cell.emptyBlurred.connect(lambda *_: None)
            self._cell.splitRequested.connect(self._on_split)

    def _on_text(self, *_):
        self.value = self._cell.text() if isinstance(self._cell, ElidedLineEdit) else self._cell.toPlainText()

    def _on_split(self, sender: QtWidgets.QWidget, head: str, tail: str) -> None:
        # Single item: keep head, ignore tail
        if isinstance(sender, ElidedLineEdit):
            blk = sender.blockSignals(True); sender.setText(head); sender.blockSignals(blk)
        else:
            sender.blockSignals(True); sender.setPlainText(head); sender.blockSignals(False)
        self.value = head

    def update_editor(self):
        if isinstance(self._cell, ElidedLineEdit):
            blk = self._cell.blockSignals(True); self._cell.setText(self.value or ""); self._cell.blockSignals(blk)
        else:
            self._cell.blockSignals(True); self._cell.setPlainText(self.value or ""); self._cell.blockSignals(False)

class FlowStrEditor(BasicEditorFactory):
    klass = _FlowStrEditor
    max_lines = Int(6)

# ---------------- DEMO: all 3 modalities, each with short and long ----------------
if __name__ == "__main__":
    from traits.api import HasTraits, Str
    from traitsui.api import Item, View

    class Demo(HasTraits):
        # One-line (plain text)
        line_short = Str("Short line")
        line_long = Str("This is a really long line of plain text that will exceed the available width in one-line mode.")

        # One-line (URL; unfocused elides middle)
        url_short = Str("https://example.com")
        url_long = Str("https://example.com/really/long/path/with/many/segments/and/a/file/name.html?with=query&and=more")

        # Wrapped (multi-line; max_lines=4, show badge when overflowing)
        wrap_short = Str("A short paragraph that fits well.")
        wrap_long = Str("This is a much longer paragraph intended to wrap across multiple lines in the editor. "
                        "Keep typing to ensure it spans more than four lines so the overflow badge becomes visible. "
                        "The height should be an exact multiple of the line spacing to avoid partial clipping.")

        traits_view = View(
            # One-line (plain)
            Item("line_short", show_label=True, label="Line (short)", editor=FlowStrEditor(max_lines=1)),
            Item("line_long", show_label=True, label="Line (too long)", editor=FlowStrEditor(max_lines=1)),
            # One-line (URL)
            Item("url_short", show_label=True, label="URL (short)", editor=FlowStrEditor(max_lines=1)),
            Item("url_long", show_label=True, label="URL (too long)", editor=FlowStrEditor(max_lines=1)),
            # Wrapped (multi-line)
            Item("wrap_short", show_label=True, label="Wrapped (short)", editor=FlowStrEditor(max_lines=4)),
            Item("wrap_long", show_label=True, label="Wrapped (long)", editor=FlowStrEditor(max_lines=4)),
            resizable=True,
            buttons=["OK"],
            title="FlowStrEditor – height fixed (3 modalities, short vs. long)",
        )

    Demo().configure_traits()