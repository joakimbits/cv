# file: ui/flow_list_str_editor.py
from __future__ import annotations

import math
from typing import Callable, Optional

from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor
from PySide6 import QtCore, QtGui, QtWidgets


# ---------------- badge widgets ----------------

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


# ---------------- cells ----------------

class _Cell(QtWidgets.QTextEdit):
    splitRequested = QtCore.Signal(object, str, str)  # (self, head, tail)

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
        self._on_blur: Optional[Callable[[QtWidgets.QWidget], None]] = None  # set by editor
        self.document().documentLayout().documentSizeChanged.connect(self._refresh_overflow_badge)

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
        self.viewport().update()  # avoid ghost caret
        if self._on_blur:
            self._on_blur(self)

    def natural_px(self, col_w: int) -> int:
        doc = self.document()
        doc.setTextWidth(float(max(1, int(col_w))))
        lh = QtGui.QFontMetricsF(self.font()).lineSpacing() or 1.0
        wrapped = max(1, int(math.ceil(float(doc.size().height()) / lh)))
        lines = max(self._min_lines, min(wrapped, self._max_lines))
        m = self.contentsMargins()
        return int(lines * lh + m.top() + m.bottom() + self.frameWidth() * 2 + 2)

    def _refresh_overflow_badge(self) -> None:
        lh = QtGui.QFontMetricsF(self.font()).lineSpacing() or 1.0
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


class _ElidedOneLineCell(QtWidgets.QLineEdit):
    splitRequested = QtCore.Signal(object, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrame(False)
        self._on_blur: Optional[Callable[[QtWidgets.QWidget], None]] = None  # set by editor

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:  # noqa: N802
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            pos = self.cursorPosition()
            t = self.text()
            self.splitRequested.emit(self, t[:pos], t[pos:])
            e.accept()
            return
        super().keyPressEvent(e)

    def natural_px(self, col_w: int) -> int:
        fm = QtGui.QFontMetrics(self.font())
        m = self.contentsMargins()
        return int(fm.lineSpacing() + m.top() + m.bottom() + 2)

    def focusOutEvent(self, e: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(e)
        self.update()  # avoid ghost caret
        if self._on_blur:
            self._on_blur(self)

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


# --------------- multi-column layout ----------------

class _NewspaperLayout(QtWidgets.QLayout):
    _MIN_COLUMNS = 1
    _MAX_COLUMNS = 6
    _H_SPACING = 12
    _MIN_COL_WIDTH = 180

    def __init__(self, parent: Optional[QtWidgets.QWidget], on_leftover: Optional[Callable[[int], None]] = None):
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self._on_leftover = on_leftover
        self.setSpacing(self._H_SPACING)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:  # noqa: N802
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QtWidgets.QLayoutItem]:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> Optional[QtWidgets.QLayoutItem]:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def insertWidget(self, index: int, w: QtWidgets.QWidget) -> None:
        self._items.insert(max(0, min(index, len(self._items))), QtWidgets.QWidgetItem(w))
        self.invalidate()
        self.activate()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        # Required by Qt; returning a sensible default avoids the pure-virtual call.
        return QtCore.QSize(self._MIN_COL_WIDTH, 400)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        if rect.width() > 0:
            self._compute_layout(rect)

    def _compute_layout(self, rect: QtCore.QRect) -> None:
        usable_w = max(1, rect.width())
        cap_h = max(1, rect.height())
        cells = [it.widget() for it in self._items if it.widget() is not None]
        total = len(cells)

        feasible_max = max(
            self._MIN_COLUMNS,
            min(self._MAX_COLUMNS, (usable_w + self._H_SPACING) // (self._MIN_COL_WIDTH + self._H_SPACING)),
        )

        chosen_cols = self._MIN_COLUMNS
        for cols in range(self._MIN_COLUMNS, feasible_max + 1):
            col_w = max(self._MIN_COL_WIDTH, (usable_w - (cols - 1) * self._H_SPACING) // cols)
            placed = 0
            i = 0
            for _ in range(cols):
                y = rect.y()
                while i < total:
                    h = cells[i].natural_px(col_w)
                    if y > rect.y() and (y - rect.y()) + h > cap_h:
                        break
                    cells[i].setGeometry(QtCore.QRect(rect.x(), y, col_w, h))
                    cells[i].show()
                    y += h
                    placed += 1
                    i += 1
            chosen_cols = cols
            if placed >= total:
                break

        x = rect.x()
        y0 = rect.y()
        i = 0
        col_w = max(self._MIN_COL_WIDTH, (usable_w - (chosen_cols - 1) * self._H_SPACING) // chosen_cols)
        for _ in range(chosen_cols):
            y = y0
            while i < total:
                h = cells[i].natural_px(col_w)
                if y > y0 and (y - y0) + h > cap_h:
                    break
                cells[i].setGeometry(QtCore.QRect(x, y, col_w, h))
                y += h
                i += 1
            x += col_w + self._H_SPACING

        leftover = total - i
        if self._on_leftover:
            self._on_leftover(leftover)

        zero = QtCore.QRect(0, 0, 0, 0)
        for j in range(i, total):
            cells[j].setGeometry(zero)
            cells[j].hide()


# --------------- editor ----------------

class _FlowListEditor(Editor):
    """
    Enter splits (no newline). Enter at start inserts empty BEFORE; Enter at end keeps trailing empty AFTER.
    Multi-line paste splits. Delete on blur for empty cells. Guard re-entrancy during splits.
    """

    def init(self, parent):
        host = QtWidgets.QWidget(parent if isinstance(parent, QtWidgets.QWidget) else None)
        grid = QtWidgets.QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        content = QtWidgets.QWidget(host)
        list_badge = _OverflowBadge(host)
        list_badge.hide()
        grid.addWidget(content, 0, 0)
        grid.addWidget(list_badge, 0, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)

        def on_leftover(n: int) -> None:
            if n > 0:
                list_badge.set_text(f"…  {n} more")
                list_badge.show()
            else:
                list_badge.hide()

        layout = _NewspaperLayout(content, on_leftover=on_leftover)
        content.setLayout(layout)

        self.control = host
        self._layout = layout
        self._splitting = False
        self.update_editor()

    def _make_cell(self, text: str) -> QtWidgets.QWidget:
        parent = self._layout.parentWidget()
        if int(self.factory.max_lines) == 1:
            c = _ElidedOneLineCell(parent)
            c.setText(text)
        else:
            c = _Cell(parent, min_lines=1, max_lines=int(self.factory.max_lines))
            c.setPlainText(text)
        c._on_blur = self._on_cell_blur
        c.splitRequested.connect(self._split_cell)
        return c

    @QtCore.Slot(object, str, str)
    def _split_cell(self, w: QtWidgets.QWidget, head: str, tail: str) -> None:
        if self._splitting or w.parent() is None:
            return
        idx = self._layout.indexOf(w)
        if idx < 0:
            return

        self._splitting = True
        try:
            # Enter at start with no newline in tail => insert empty BEFORE
            if head == "" and ("\n" not in tail):
                self.value.insert(idx, "")
                self._layout.insertWidget(idx, self._make_cell(""))
                def apply_before():
                    it = self._layout.itemAt(idx)
                    if it:
                        nw = it.widget()
                        nw.setFocus(QtCore.Qt.TabFocusReason)
                        if isinstance(nw, _ElidedOneLineCell):
                            nw.setCursorPosition(0)
                        elif isinstance(nw, _Cell):
                            tc = nw.textCursor(); tc.movePosition(QtGui.QTextCursor.Start); nw.setTextCursor(tc)
                    w.clearFocus()
                    (w.viewport().update() if isinstance(w, _Cell) else w.update())
                    self._layout.activate()
                QtCore.QTimer.singleShot(0, apply_before)
                return

            tails = tail.split("\n")  # keep trailing empty

            # Update current widget without echoing signals
            if isinstance(w, _ElidedOneLineCell):
                prev = w.blockSignals(True); w.setText(head); w.blockSignals(prev)
            elif isinstance(w, _Cell):
                w.blockSignals(True); w.setPlainText(head); w.blockSignals(False)
            self.value[idx] = head

            insert_at = idx + 1
            for seg in tails:
                self.value.insert(insert_at, seg)
                self._layout.insertWidget(insert_at, self._make_cell(seg))
                insert_at += 1

            def apply_after():
                if tails:
                    it = self._layout.itemAt(idx + 1)
                    if it:
                        nxt = it.widget()
                        nxt.setFocus(QtCore.Qt.TabFocusReason)
                        if isinstance(nxt, _ElidedOneLineCell):
                            nxt.setCursorPosition(0)
                        elif isinstance(nxt, _Cell):
                            tc = nxt.textCursor(); tc.movePosition(QtGui.QTextCursor.Start); nxt.setTextCursor(tc)
                w.clearFocus()
                (w.viewport().update() if isinstance(w, _Cell) else w.update())
                self._layout.activate()
            QtCore.QTimer.singleShot(0, apply_after)
        finally:
            self._splitting = False

    def _on_cell_blur(self, w: QtWidgets.QWidget) -> None:
        if self._splitting:
            return
        idx = self._layout.indexOf(w)
        if idx < 0:
            return

        text = w.text() if isinstance(w, _ElidedOneLineCell) else (w.toPlainText() if isinstance(w, _Cell) else "")
        if text != "":
            return

        del self.value[idx]
        it = self._layout.takeAt(idx)
        ww = it.widget() if it else None
        if ww:
            ww.setParent(None)
            ww.deleteLater()

        fw = QtWidgets.QApplication.focusWidget()
        if fw and self.control and self.control.isAncestorOf(fw) and fw is not ww:
            return

        nxt = self._layout.itemAt(idx).widget() if idx < self._layout.count() else None
        prv = self._layout.itemAt(idx - 1).widget() if idx - 1 >= 0 else None
        (nxt or prv or self.control).setFocus(QtCore.Qt.TabFocusReason)

    def update_editor(self):
        if self._layout.count() == 0:
            for v in self.value:
                self._layout.addWidget(self._make_cell(v))


class FlowListStrEditor(BasicEditorFactory):
    klass = _FlowListEditor
    max_lines = Int(6)


# ---------------- demo ----------------

if __name__ == "__main__":
    from traits.api import HasTraits, List, Str
    from traitsui.api import Item, View

    class Demo(HasTraits):
        one_line = List(Str, [
            "https://example.com/really/long/path/1/file.ext",
            "A longer text in cell 2 that may not fit the cell",
        ])
        multi = List(Str, ["A longer wrapped text that spans several lines. "] * 2 + [f"Line {i}" for i in range(1, 10)])

        traits_view = View(
            Item("one_line", show_label=False, editor=FlowListStrEditor(max_lines=1)),
            Item("multi", show_label=False, editor=FlowListStrEditor(max_lines=4)),
            resizable=True,
            buttons=["OK"],
            title="FlowListStrEditor (fixed sizeHint)",
        )

    Demo().configure_traits()
