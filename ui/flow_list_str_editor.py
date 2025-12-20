# file: ui/flow_list_str_editor.py
from __future__ import annotations

import math
from typing import Callable, Optional

from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor
from PySide6 import QtCore, QtGui, QtWidgets

from ui.str_cell_editor import (
    _OverflowBadge,
    CellTextEdit,
    ElidedLineEdit,
    make_cell,
)
from ui.cell_base import CellProtocol

# ---------- multi-column layout ----------

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

# ---------- list editor (strings) ----------

class _FlowListStrEditor(Editor):
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

    def _wire_cell(self, w: CellProtocol) -> None:
        w.splitRequested.connect(self._split_cell)          # type: ignore[attr-defined]
        w.emptyBlurred.connect(self._on_cell_empty_blur)    # type: ignore[attr-defined]

    def _make_cell(self, text: str) -> CellProtocol:
        parent = self._layout.parentWidget()
        w = make_cell(parent, max_lines=int(self.factory.max_lines), text=text)
        self._wire_cell(w)
        return w

    # ---- split handler ----

    @QtCore.Slot(object, object, object)
    def _split_cell(self, sender: QtWidgets.QWidget, head: str, tail: str) -> None:
        if self._splitting or sender.parent() is None:
            return
        idx = self._layout.indexOf(sender)
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
                        if isinstance(nw, ElidedLineEdit):
                            nw.setCursorPosition(0)
                        elif isinstance(nw, CellTextEdit):
                            tc = nw.textCursor(); tc.movePosition(QtGui.QTextCursor.Start); nw.setTextCursor(tc)
                    sender.clearFocus()
                    (sender.viewport().update() if isinstance(sender, CellTextEdit) else sender.update())
                    self._layout.activate()
                QtCore.QTimer.singleShot(0, apply_before)
                return

            tails = tail.split("\n")  # keep trailing empty

            # Update sender text without echo
            if isinstance(sender, ElidedLineEdit):
                prev = sender.blockSignals(True); sender.setText(head); sender.blockSignals(prev)
            elif isinstance(sender, CellTextEdit):
                sender.blockSignals(True); sender.setPlainText(head); sender.blockSignals(False)
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
                        if isinstance(nxt, ElidedLineEdit):
                            nxt.setCursorPosition(0)
                        elif isinstance(nxt, CellTextEdit):
                            tc = nxt.textCursor(); tc.movePosition(QtGui.QTextCursor.Start); nxt.setTextCursor(tc)
                sender.clearFocus()
                (sender.viewport().update() if isinstance(sender, CellTextEdit) else sender.update())
                self._layout.activate()
            QtCore.QTimer.singleShot(0, apply_after)
        finally:
            self._splitting = False

    # ---- delete-on-blur ----

    @QtCore.Slot(object)
    def _on_cell_empty_blur(self, sender: QtWidgets.QWidget) -> None:
        if self._splitting:
            return
        idx = self._layout.indexOf(sender)
        if idx < 0:
            return

        # Safety: confirm emptiness
        text = sender.text() if isinstance(sender, ElidedLineEdit) else (sender.toPlainText() if isinstance(sender, CellTextEdit) else "")
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

    # ---- traits glue ----

    def update_editor(self):
        if self._layout.count() == 0:
            for v in self.value:
                self._layout.addWidget(self._make_cell(v))

class FlowListStrEditor(BasicEditorFactory):
    klass = _FlowListStrEditor
    max_lines = Int(6)

# Demo
if __name__ == "__main__":
    from traits.api import HasTraits, List, Str
    from traitsui.api import Item, View

    class Demo(HasTraits):
        one_line = List(Str, [
            "https://example.com/really/long/path/1/file.ext",
            "A longer text in cell 2 that may not fit the cell",
        ])
        multi = List(Str, ["This is a longer wrapped line. "] * 2 + [f"Line {i}" for i in range(1, 10)])

        traits_view = View(
            Item("one_line", show_label=False, editor=FlowListStrEditor(max_lines=1)),
            Item("multi", show_label=False, editor=FlowListStrEditor(max_lines=4)),
            resizable=True,
            buttons=["OK"],
            title="FlowListStrEditor (generic cell contract)",
        )

    Demo().configure_traits()
