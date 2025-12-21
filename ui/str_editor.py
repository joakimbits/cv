# file: ui/str_editor.py
from __future__ import annotations

import math
from typing import Literal

from PySide6 import QtCore, QtGui, QtWidgets
from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor


# ---------- helpers (integrated) ----------

ElideMode = Literal["right", "middle", "left", "auto"]

class _LineElide(QtCore.QObject):
    """Unfocused elision for QLineEdit."""
    def __init__(self, le: QtWidgets.QLineEdit, *, mode: ElideMode = "auto"):
        super().__init__(le)
        self._le = le
        self._mode = mode
        le.installEventFilter(self)
        le.textChanged.connect(le.update)
        le.cursorPositionChanged.connect(le.update)
        le.selectionChanged.connect(le.update)

    def _chosen_mode(self, text: str) -> QtCore.Qt.TextElideMode:
        m = self._mode
        if m == "auto":
            m = "middle" if "://" in text else "right"
        return {"right": QtCore.Qt.ElideRight, "middle": QtCore.Qt.ElideMiddle, "left": QtCore.Qt.ElideLeft}[m]

    def _paint_elided(self) -> None:
        le = self._le
        p = QtGui.QPainter(le)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        p.fillRect(le.rect(), le.palette().brush(QtGui.QPalette.Base))
        r = le.contentsRect().adjusted(2, 0, -2, 0)
        fm = le.fontMetrics()
        elided = fm.elidedText(le.text(), self._chosen_mode(le.text()), max(1, r.width()))
        p.setPen(le.palette().color(QtGui.QPalette.Text))
        p.drawText(r, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, elided)

    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if obj is self._le:
            t = ev.type()
            if t in (QtCore.QEvent.FocusIn, QtCore.QEvent.FocusOut, QtCore.QEvent.Resize):
                self._le.update()
            if t == QtCore.QEvent.Paint and not self._le.hasFocus() and self._le.echoMode() == QtWidgets.QLineEdit.Normal:
                self._paint_elided()
                return True
        return super().eventFilter(obj, ev)


class _HeightSync(QtCore.QObject):
    """Keep widget height == natural_px(host_width); defer until width is real; clamp via min==max."""
    def __init__(self, host: QtWidgets.QWidget, w: QtWidgets.QWidget):
        super().__init__(host)
        self._host = host
        self._w = w
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
    def sync(self, *_) -> None:
        width = int(self._host.width() or self._w.width() or 0)
        if width < 10:
            QtCore.QTimer.singleShot(0, self.sync)
            return
        height = int(self._w.natural_px(width)) if hasattr(self._w, "natural_px") else self._w.sizeHint().height()
        self._w.setMinimumHeight(height)
        self._w.setMaximumHeight(height)

    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if ev.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            self.sync()
        return False


class _OverflowBadge(QtWidgets.QWidget):
    """Tiny badge widget."""
    def __init__(self, parent: QtWidgets.QWidget | None = None):
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


def _count_wrapped_lines(doc: QtGui.QTextDocument) -> int:
    """
    Return the exact visible line count by summing per-block layout line counts.
    Avoids overcount from documentSize() (which includes extra leading/padding).
    """
    lines = 0
    block = doc.firstBlock()
    while block.isValid():
        layout = block.layout()
        if layout is None:
            # Force layout if not ready yet
            doc.documentLayout().update()
            layout = block.layout()
        cnt = layout.lineCount() if layout is not None else 1
        lines += max(1, cnt)
        block = block.next()
    return max(1, lines)


class _OverflowBadgeCtl(QtCore.QObject):
    """Attach badge to a QTextEdit; shows '… N more' when wrapped lines exceed max_lines."""
    def __init__(self, edit: QtWidgets.QTextEdit, *, max_lines: int):
        super().__init__(edit)
        self._edit = edit
        self._max = int(max_lines)
        self._badge = _OverflowBadge(edit)
        self._badge.hide()
        edit.installEventFilter(self)
        edit.document().documentLayout().documentSizeChanged.connect(self._refresh)

        QtCore.QTimer.singleShot(0, self._refresh)

    def _refresh(self) -> None:
        doc = self._edit.document()
        wrapped = _count_wrapped_lines(doc)
        extra = max(0, wrapped - self._max)
        if extra <= 0:
            self._badge.hide()
            return
        self._badge.set_text(f"… {extra} more")
        sz = self._badge.sizeHint()
        cr = self._edit.contentsRect()
        self._badge.setGeometry(cr.right() - sz.width() - 2, cr.bottom() - sz.height() - 2, sz.width(), sz.height())
        self._badge.show()

    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if obj is self._edit and ev.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            self._refresh()
        return False


# ---------- widgets ----------

class _LineStr(QtWidgets.QLineEdit):
    """One-line Str with exact natural height."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrame(False)

    def natural_px(self, col_w: int) -> int:
        fm = QtGui.QFontMetricsF(self.font())
        lh = fm.lineSpacing() or 1.0
        m = self.contentsMargins()
        return int(math.ceil(lh + m.top() + m.bottom()))


class _WrapStr(QtWidgets.QTextEdit):
    """Wrapped Str with integral height up to max_lines."""
    def __init__(self, parent=None, *, max_lines: int = 4):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self._max_lines = max(1, int(max_lines))
        self.document().setDocumentMargin(0)

    def natural_px(self, col_w: int) -> int:
        doc = self.document()
        doc.setTextWidth(float(max(1, int(col_w))))
        fm = QtGui.QFontMetricsF(self.font())
        lh = fm.lineSpacing() or 1.0

        # Exact wrapped line count (no phantom line)
        wrapped = _count_wrapped_lines(doc)
        lines = min(wrapped, self._max_lines)

        m = self.contentsMargins()
        border = m.top() + m.bottom() + self.frameWidth() * 2  # 0 with NoFrame
        return int(math.ceil(lines * lh + border))


# ---------- TraitsUI Str editor ----------

class _StrEditor(Editor):
    """Single Str editor; one-line (unfocused elide) or wrapped (auto-height up to max_lines + badge)."""
    def init(self, parent):
        host = QtWidgets.QWidget(parent if isinstance(parent, QtWidgets.QWidget) else None)
        layout = QtWidgets.QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        max_lines = int(self.factory.max_lines)
        if max_lines == 1:
            w = _LineStr(host)
            w.setText(self.value or "")
            sp = w.sizePolicy(); sp.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed); w.setSizePolicy(sp)
            self._elide = _LineElide(w, mode="auto")
            w.textEdited.connect(self._on_line_changed)
        else:
            w = _WrapStr(host, max_lines=max_lines)
            w.setPlainText(self.value or "")
            sp = w.sizePolicy(); sp.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed); w.setSizePolicy(sp)
            self._badge = _OverflowBadgeCtl(w, max_lines=max_lines)  # only for wrapped
            w.textChanged.connect(self._on_wrap_changed)

        layout.addWidget(w)
        self._sizer = _HeightSync(host, w)  # exact integral height
        self._w = w
        self.control = host

    def _on_line_changed(self, *_):
        self.value = self._w.text()
        self._sizer.sync()

    def _on_wrap_changed(self, *_):
        self.value = self._w.toPlainText()
        self._sizer.sync()

    def update_editor(self):
        if isinstance(self._w, _LineStr):
            blk = self._w.blockSignals(True); self._w.setText(self.value or ""); self._w.blockSignals(blk)
        else:
            self._w.blockSignals(True); self._w.setPlainText(self.value or ""); self._w.blockSignals(False)
        self._sizer.sync()


class StrEditor(BasicEditorFactory):
    """Use: Item('field', editor=StrEditor(max_lines=1 or >1))"""
    klass = _StrEditor
    max_lines = Int(4)


# ---------- demo ----------
if __name__ == "__main__":
    from traits.api import HasTraits, Str
    from traitsui.api import Item, View

    class Demo(HasTraits):
        line_short = Str("Short line")
        line_long  = Str("This is a really long line of plain text that should elide when unfocused.")
        url_short  = Str("https://example.com")
        url_long   = Str("https://example.com/really/long/path/with/many/segments/and/a/file.html?with=query&and=more")
        wrap_short = Str("Short paragraph that fits.")
        wrap_long  = Str(
            "This is a much longer paragraph intended to wrap across multiple lines in the editor. "
            "It should grow with content up to max_lines and stop there. Height should remain an exact "
            "multiple of the line spacing to avoid any partly-clipped lines."
        )

        traits_view = View(
            Item("line_short", label="Line (short)",       editor=StrEditor(max_lines=1), show_label=True),
            Item("line_long",  label="Line (too long)",    editor=StrEditor(max_lines=1), show_label=True),
            Item("url_short",  label="URL (short)",        editor=StrEditor(max_lines=1), show_label=True),
            Item("url_long",   label="URL (too long)",     editor=StrEditor(max_lines=1), show_label=True),
            Item("wrap_short", label="Wrapped (short)",    editor=StrEditor(max_lines=4), show_label=True),
            Item("wrap_long",  label="Wrapped (too long)", editor=StrEditor(max_lines=4), show_label=True),
            resizable=True, buttons=["OK"], title="StrEditor – fixed phantom-line issue",
        )

    Demo().configure_traits()
