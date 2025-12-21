# file: flow_list_str_editor.py
from __future__ import annotations

from typing import Callable, Optional, Set, Tuple

from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.group import HGroup
from traitsui.qt.editor import Editor
from PySide6 import QtCore, QtGui, QtWidgets

# Project-local modules
from ui.cells_str import CellTextEdit, ElidedLineEdit
from ui.cell_protocol import CellProtocol
from ui.badge import OverflowBadge, OverflowBadgeCtl
from ui.elide import attach_line_elide


# -------------------------- Paste-aware one-line cell --------------------------

class _PasteAwareLineEdit(ElidedLineEdit):
    """One-line cell: compose-then-split on multi-line paste; emit splitRequested(sender, head, tail)."""

    splitRequested = QtCore.Signal(object, str, str)  # sender, head, tail

    def _try_split_from_text(self, text: str) -> bool:
        if not text or (("\n" not in text) and ("\r" not in text)):
            return False
        t = text.replace("\r\n", "\n").replace("\r", "\n")

        pos = self.cursorPosition()
        old = self.text()
        before, after = old[:pos], old[pos:]

        composed = before + t + after
        lines = composed.split("\n")  # keeps trailing '' when composed endswith '\n'
        head = lines[0]
        tail = "\n".join(lines[1:])   # '' -> empty next cell (enter-at-end-like)

        self.splitRequested.emit(self, head, tail)
        return True

    def keyPressEvent(self, ev: QtGui.QKeyEvent) -> None:
        ctrl = bool(ev.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier))
        if (ctrl and ev.key() == QtCore.Qt.Key_V) or \
           (ev.key() == QtCore.Qt.Key_Insert and (ev.modifiers() & QtCore.Qt.ShiftModifier)):
            txt = QtWidgets.QApplication.clipboard().text()
            if self._try_split_from_text(txt):
                return
        super().keyPressEvent(ev)

    def paste(self) -> None:
        txt = QtWidgets.QApplication.clipboard().text()
        if self._try_split_from_text(txt):
            return
        super().paste()


# -------------------------- Paste-aware wrapped cell --------------------------

class _PasteAwareTextEdit(CellTextEdit):
    """Wrapped cell: compose-then-split on paste; emit existing splitRequested(sender, head, tail)."""

    def _emit_split(self, head: str, tail: str) -> None:
        # rely on CellTextEdit providing the signal
        self.splitRequested.emit(self, head, tail)  # type: ignore[attr-defined]

    def _try_split_from_text(self, text: str) -> bool:
        if not text or (("\n" not in text) and ("\r" not in text)):
            return False
        t = text.replace("\r\n", "\n").replace("\r", "\n")

        cur = self.textCursor()
        a, b = sorted((cur.position(), cur.anchor()))
        old = self.toPlainText()
        before, after = old[:a], old[b:]

        composed = before + t + after
        lines = composed.split("\n")    # preserves trailing ''
        head = lines[0]
        tail = "\n".join(lines[1:])

        self._emit_split(head, tail)
        return True

    def insertFromMimeData(self, source: QtCore.QMimeData) -> None:  # type: ignore[override]
        txt = source.text() if source is not None else ""
        if self._try_split_from_text(txt):
            return
        super().insertFromMimeData(source)

    def keyPressEvent(self, ev: QtGui.QKeyEvent) -> None:
        ctrl = bool(ev.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier))
        if (ctrl and ev.key() == QtCore.Qt.Key_V) or \
           (ev.key() == QtCore.Qt.Key_Insert and (ev.modifiers() & QtCore.Qt.ShiftModifier)):
            txt = QtWidgets.QApplication.clipboard().text()
            if self._try_split_from_text(txt):
                return
        super().keyPressEvent(ev)

    def paste(self) -> None:
        txt = QtWidgets.QApplication.clipboard().text()
        if self._try_split_from_text(txt):
            return
        super().paste()


# -------------------------- Cell wrapper --------------------------

class _CellWrap(QtWidgets.QWidget):
    """Wrapper paints persistent selection border; keeps focus on inner cell."""
    PAD_H = 4
    PAD_W = 4

    def __init__(self, inner: QtWidgets.QWidget, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.inner = inner
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(self.PAD_W, self.PAD_H, self.PAD_W, self.PAD_H)
        lay.setSpacing(0)
        lay.addWidget(inner)
        sp = self.sizePolicy()
        sp.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed)
        self.setSizePolicy(sp)
        self.setAutoFillBackground(False)

    def natural_px(self, col_w: int) -> int:
        pad = self.PAD_H * 2
        inner_w = max(1, col_w - 2 * self.PAD_W)
        if hasattr(self.inner, "natural_px"):
            return int(self.inner.natural_px(inner_w) + pad)
        return int(self.inner.sizeHint().height() + pad)

    def paintEvent(self, ev: QtGui.QPaintEvent) -> None:
        super().paintEvent(ev)
        if bool(self.property("cellSelected")):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            col = self.palette().color(QtGui.QPalette.Highlight)
            pen = QtGui.QPen(col); pen.setWidth(2)
            p.setPen(pen); p.setBrush(QtCore.Qt.NoBrush)
            r = self.rect().adjusted(1, 1, -1, -1)
            p.drawRoundedRect(r, 6, 6)
            p.end()


# -------------------------- Flow layout --------------------------

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
        self.invalidate(); self.activate()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(self._MIN_COL_WIDTH, 400)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        if rect.width() > 0:
            self._compute_layout(rect)

    def _compute_layout(self, rect: QtCore.QRect) -> None:
        usable_w = max(1, rect.width())
        cap_h = max(1, rect.height())
        wraps = [it.widget() for it in self._items if it.widget() is not None]
        total = len(wraps)

        feasible_max = max(
            self._MIN_COLUMNS,
            min(self._MAX_COLUMNS, (usable_w + self._H_SPACING) // (self._MIN_COL_WIDTH + self._H_SPACING)),
        )

        chosen_cols = self._MIN_COLUMNS
        for cols in range(self._MIN_COLUMNS, feasible_max + 1):
            col_w = max(self._MIN_COL_WIDTH, (usable_w - (cols - 1) * self._H_SPACING) // cols)
            placed = 0; i = 0
            for _ in range(cols):
                y = rect.y()
                while i < total:
                    h = wraps[i].natural_px(col_w)  # type: ignore[attr-defined]
                    if y > rect.y() and (y - rect.y()) + h > cap_h:
                        break
                    wraps[i].setGeometry(QtCore.QRect(rect.x(), y, col_w, h))
                    wraps[i].show()
                    y += h; placed += 1; i += 1
            chosen_cols = cols
            if placed >= total:
                break

        x = rect.x(); y0 = rect.y(); i = 0
        col_w = max(self._MIN_COL_WIDTH, (usable_w - (chosen_cols - 1) * self._H_SPACING) // chosen_cols)
        for _ in range(chosen_cols):
            y = y0
            while i < total:
                h = wraps[i].natural_px(col_w)  # type: ignore[attr-defined]
                if y > y0 and (y - y0) + h > cap_h:
                    break
                wraps[i].setGeometry(QtCore.QRect(x, y, col_w, h))
                y += h; i += 1
            x += col_w + self._H_SPACING

        leftover = total - i
        if self._on_leftover:
            self._on_leftover(leftover)

        zero = QtCore.QRect(0, 0, 0, 0)
        for j in range(i, total):
            wraps[j].setGeometry(zero); wraps[j].hide()


# -------------------------- Cell selection --------------------------

class _CellSelection(QtCore.QObject):
    """Whole-cell selection. Copy always appends trailing '\\n'."""
    def __init__(self, editor: "_FlowListStrEditor", content: QtWidgets.QWidget):
        super().__init__(content)
        self._ed = editor
        self._content = content
        self._selected: Set[int] = set()
        self._anchor: int | None = None
        self._drag_ctrl = False
        self._dragging = False
        self._last_idx: int | None = None
        self._swallow_next_delete_or_cut = False

        content.installEventFilter(self)
        editor.control.installEventFilter(self)
        win = editor.control.window()
        if win is not None:
            win.installEventFilter(self)

        self._sc_esc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), editor.control)
        self._sc_esc.setContext(QtCore.Qt.WindowShortcut)
        self._sc_esc.activated.connect(self.clear)

    def attach_cell(self, wrap: _CellWrap) -> None:
        wrap.installEventFilter(self)
        cell = wrap.inner
        cell.installEventFilter(self)
        if isinstance(cell, CellTextEdit):
            cell.viewport().installEventFilter(self)

    def clear(self) -> None:
        self._apply(set()); self._selected.clear(); self._anchor = None

    def select_all(self) -> None:
        idxs = {i for i in range(self._ed._layout.count())}
        self._apply(idxs); self._selected = idxs
        self._anchor = 0 if self._ed._layout.count() else None

    def _copy_cells_to_clipboard(self, data: str) -> None:
        QtWidgets.QApplication.clipboard().setText(data, QtGui.QClipboard.Clipboard)

    def copy(self) -> None:
        if not self._selected:
            return
        selected_indices = [i for i in range(self._ed._layout.count()) if i in self._selected]
        out: list[str] = []
        for i in selected_indices:
            wrap = self._ed._layout.itemAt(i).widget()
            cell = wrap.inner if isinstance(wrap, _CellWrap) else wrap
            if isinstance(cell, ElidedLineEdit):
                out.append(cell.text())
            elif isinstance(cell, CellTextEdit):
                out.append(cell.toPlainText())
        data = "\n".join(out) + "\n"  # always final newline
        self._copy_cells_to_clipboard(data)

    def cut(self) -> None:
        if not self._selected:
            return
        self.copy()
        self._ed._delete_selected_cells(sorted(self._selected))
        self._swallow_next_delete_or_cut = True

    def _idx_from_global(self, gpt: QtCore.QPoint) -> int | None:
        pt = self._content.mapFromGlobal(gpt)
        for i in range(self._ed._layout.count()):
            w = self._ed._layout.itemAt(i).widget()
            if w.isVisible() and w.geometry().contains(pt):
                return i
        return None

    def _hit_index(self, obj: QtCore.QObject, pt: QtCore.QPoint) -> int | None:
        wrap = None
        if isinstance(obj, _CellWrap):
            wrap = obj
        elif isinstance(obj, (ElidedLineEdit, CellTextEdit)):
            p = obj.parent()
            if isinstance(p, _CellWrap):
                wrap = p
        elif isinstance(obj, QtWidgets.QWidget):
            p = obj.parent()
            if isinstance(p, CellTextEdit):
                gp = p.parent()
                if isinstance(gp, _CellWrap):
                    wrap = gp
        if wrap is None and obj is self._content:
            for i in range(self._ed._layout.count()):
                w = self._ed._layout.itemAt(i).widget()
                if w.isVisible() and w.geometry().contains(pt):
                    wrap = w; break
        if wrap is None:
            return None
        return self._ed._layout.indexOf(wrap)

    def _apply(self, indices: Set[int]) -> None:
        for i in range(self._ed._layout.count()):
            wrap = self._ed._layout.itemAt(i).widget()
            want = i in indices
            if wrap.property("cellSelected") != want:
                wrap.setProperty("cellSelected", want)
                wrap.update()

    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if ev.type() == QtCore.QEvent.ShortcutOverride and isinstance(ev, QtGui.QKeyEvent):
            ctrl = bool(ev.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier))
            if ctrl and ev.key() == QtCore.Qt.Key_C:
                if self._selected:
                    self.copy(); ev.accept(); return True
                return False
            if ctrl and ev.key() == QtCore.Qt.Key_X:
                if self._selected:
                    self.cut(); ev.accept(); return True
                return False
            if ctrl and ev.key() == QtCore.Qt.Key_A:
                if self._selected:
                    self.select_all(); ev.accept(); return True
                return False
            if ev.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                if self._selected:
                    self._ed._delete_selected_cells(sorted(self._selected))
                    self._swallow_next_delete_or_cut = True
                    ev.accept(); return True
                return False
            return False

        if ev.type() == QtCore.QEvent.KeyPress and isinstance(ev, QtGui.QKeyEvent):
            if self._swallow_next_delete_or_cut and ev.key() in (
                QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace, QtCore.Qt.Key_X
            ):
                return True
            return False

        if ev.type() == QtCore.QEvent.KeyRelease and isinstance(ev, QtGui.QKeyEvent):
            if self._swallow_next_delete_or_cut and ev.key() in (
                QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace, QtCore.Qt.Key_X
            ):
                self._swallow_next_delete_or_cut = False
                return True
            return False

        def idx_from_event(e: QtGui.QMouseEvent) -> int | None:
            if obj in (self._content,):
                return self._hit_index(obj, e.position().toPoint())
            return self._idx_from_global(e.globalPosition().toPoint())

        if ev.type() == QtCore.QEvent.MouseButtonPress and isinstance(ev, QtGui.QMouseEvent):
            if ev.button() != QtCore.Qt.LeftButton:
                return False
            idx = self._hit_index(obj, ev.position().toPoint()) if obj is not self._ed.control.window() else idx_from_event(ev)

            mods = ev.modifiers()
            self._drag_ctrl = bool(mods & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier))
            self._dragging = True
            self._last_idx = None
            shift = bool(mods & QtCore.Qt.ShiftModifier)

            if idx is not None and not self._drag_ctrl and not shift:
                self.clear(); self._anchor = idx; return False
            if idx is None and not self._drag_ctrl and not shift:
                self.clear(); return True
            if shift and idx is not None and self._anchor is not None:
                a, b = sorted((self._anchor, idx))
                new_sel = set(range(a, b + 1))
                if self._drag_ctrl: new_sel |= self._selected
                self._apply(new_sel); self._selected = new_sel; self._last_idx = idx
                return True
            if self._drag_ctrl and idx is not None:
                new_sel = set(self._selected)
                if idx in new_sel: new_sel.remove(idx)
                else: new_sel.add(idx)
                self._apply(new_sel); self._selected = new_sel
                if self._anchor is None and new_sel: self._anchor = idx
                self._last_idx = idx
                return True
            if shift and idx is not None and self._anchor is None:
                self._anchor = idx; return False

        if ev.type() == QtCore.QEvent.MouseMove and isinstance(ev, QtGui.QMouseEvent):
            if not (self._dragging and self._drag_ctrl and (ev.buttons() & QtCore.Qt.LeftButton)):
                return False
            idx = self._hit_index(obj, ev.position().toPoint()) if obj is not self._ed.control.window() else self._idx_from_global(ev.globalPosition().toPoint())
            if idx is None or idx == self._last_idx:
                return False
            new_sel = set(self._selected)
            if idx in new_sel: new_sel.remove(idx)
            else: new_sel.add(idx)
            self._apply(new_sel); self._selected = new_sel; self._last_idx = idx
            return True

        if ev.type() == QtCore.QEvent.MouseButtonRelease and isinstance(ev, QtGui.QMouseEvent):
            if ev.button() == QtCore.Qt.LeftButton:
                self._dragging = False; self._drag_ctrl = False; self._last_idx = None
                return False

        return False


# -------------------------- Editor --------------------------

class _FlowListStrEditor(Editor):
    """
    List(Str) with:
      • Enter splits; Enter at start inserts empty BEFORE
      • Delete on blur for empty cells
      • 1-line: elide on unfocus; Wrapped: overflow badge
      • Auto-height via cell.natural_px (through wrapper)
      • Selection: Shift-click range, Ctrl/Cmd-click toggle, Ctrl-drag sweep,
        Ctrl+A (conditional), Ctrl+X cut, Del/Backspace remove
      • Paste is cell-native; one-line and wrapped both compose-then-split and signal.
    """

    def init(self, parent):
        host = QtWidgets.QWidget(parent if isinstance(parent, QtWidgets.QWidget) else None)
        grid = QtWidgets.QGridLayout(host); grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(0)

        content = QtWidgets.QWidget(host)
        self._list_badge = OverflowBadge(host); self._list_badge.hide()
        grid.addWidget(content, 0, 0); grid.addWidget(self._list_badge, 0, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)

        def on_leftover(n: int) -> None:
            if n > 0:
                self._list_badge.set_text(f"…  {n} more"); self._list_badge.show()
            else:
                self._list_badge.hide()

        layout = _NewspaperLayout(content, on_leftover=on_leftover)
        content.setLayout(layout)

        self.control = host
        self._layout = layout
        self._splitting = False

        self._cellsel = _CellSelection(self, content)

        self.update_editor()

    def _wire_cell(self, cell: CellProtocol) -> None:
        cell.splitRequested.connect(self._on_split)       # why: Enter/paste split
        cell.emptyBlurred.connect(self._on_empty_blur)    # why: delete on blur of empty

    def _wrap_cell(self, cell: CellProtocol) -> _CellWrap:
        wrap = _CellWrap(cell, parent=self._layout.parentWidget())
        self._cellsel.attach_cell(wrap)
        return wrap

    def _make_cell(self, text: str) -> _CellWrap:
        parent = self._layout.parentWidget()
        if int(self.factory.max_lines) == 1:
            cell = _PasteAwareLineEdit(parent)
            cell.setText(text)
        else:
            cell = _PasteAwareTextEdit(parent)
            cell.setPlainText(text)

        if isinstance(cell, ElidedLineEdit):
            attach_line_elide(cell)
        elif isinstance(cell, CellTextEdit):
            OverflowBadgeCtl(cell, max_lines=int(self.factory.max_lines))

        sp = cell.sizePolicy(); sp.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed); cell.setSizePolicy(sp)
        self._wire_cell(cell)
        return self._wrap_cell(cell)

    def _index_of(self, w: QtWidgets.QWidget) -> int:
        wrap = self._wrap_of(w)
        return self._layout.indexOf(wrap) if wrap else -1

    def _wrap_of(self, w: QtWidgets.QWidget) -> Optional[_CellWrap]:
        if isinstance(w, _CellWrap):
            return w
        p = w.parent()
        return p if isinstance(p, _CellWrap) else None

    def _widget_at(self, idx: int) -> Tuple[_CellWrap, CellProtocol]:
        it = self._layout.itemAt(idx)
        wrap = it.widget() if it else None
        cell = wrap.inner if isinstance(wrap, _CellWrap) else None
        return wrap, cell  # type: ignore[return-value]

    @QtCore.Slot(object, str, str)
    def _on_split(self, sender: QtWidgets.QWidget, head: str, tail: str) -> None:
        if self._splitting or sender.parent() is None:
            return
        idx = self._index_of(sender)
        if idx < 0:
            return

        self._cellsel.clear()
        self._splitting = True
        try:
            if head == "" and ("\n" not in tail):
                self.value.insert(idx, "")
                self._layout.insertWidget(idx, self._make_cell(""))
                QtCore.QTimer.singleShot(0, lambda: self._focus_idx(idx, sender))
                return

            if isinstance(sender, ElidedLineEdit):
                blk = sender.blockSignals(True); sender.setText(head); sender.blockSignals(blk)
            elif isinstance(sender, CellTextEdit):
                sender.blockSignals(True); sender.setPlainText(head); sender.blockSignals(False)
            self.value[idx] = head

            parts = tail.split("\n")
            ins = idx + 1
            last_idx = None
            for seg in parts:
                self.value.insert(ins, seg)
                self._layout.insertWidget(ins, self._make_cell(seg))
                last_idx = ins; ins += 1

            tgt = last_idx if last_idx is not None else idx
            QtCore.QTimer.singleShot(0, lambda: self._focus_idx(tgt, sender))
        finally:
            self._splitting = False

    @QtCore.Slot(object)
    def _on_empty_blur(self, sender: QtWidgets.QWidget) -> None:
        if self._splitting:
            return
        idx = self._index_of(sender)
        if idx < 0:
            return

        if isinstance(sender, ElidedLineEdit):
            txt = sender.text()
        elif isinstance(sender, CellTextEdit):
            txt = sender.toPlainText()
        else:
            txt = ""
        if txt != "":
            return

        self._cellsel.clear()

        del self.value[idx]
        item = self._layout.takeAt(idx)
        wrap = item.widget() if item else None
        if wrap:
            wrap.setParent(None); wrap.deleteLater()

        nxt_wrap = self._layout.itemAt(idx).widget() if idx < self._layout.count() else None
        prv_wrap = self._layout.itemAt(idx - 1).widget() if idx - 1 >= 0 else None
        target = nxt_wrap or prv_wrap
        if target and isinstance(target, _CellWrap):
            target.inner.setFocus(QtCore.Qt.TabFocusReason)
        else:
            self.control.setFocus(QtCore.Qt.TabFocusReason)

    def _delete_selected_cells(self, indices_sorted: list[int]) -> None:
        if not indices_sorted:
            return
        for idx in sorted(indices_sorted, reverse=True):
            if 0 <= idx < len(self.value):
                del self.value[idx]
                item = self._layout.takeAt(idx)
                wrap = item.widget() if item else None
                if wrap:
                    wrap.setParent(None); wrap.deleteLater()
        focus_at = min(max(0, indices_sorted[0]), self._layout.count() - 1)
        self._cellsel.clear()
        if 0 <= focus_at < self._layout.count():
            wrap = self._layout.itemAt(focus_at).widget()
            if isinstance(wrap, _CellWrap):
                wrap.inner.setFocus(QtCore.Qt.TabFocusReason)
        else:
            self.control.setFocus(QtCore.Qt.TabFocusReason)

    def _focus_idx(self, idx: int, old_inner: QtWidgets.QWidget) -> None:
        it = self._layout.itemAt(idx)
        wrap = it.widget() if it else None
        if not isinstance(wrap, _CellWrap):
            return
        nxt = wrap.inner
        nxt.setFocus(QtCore.Qt.TabFocusReason)
        if isinstance(nxt, ElidedLineEdit):
            nxt.setCursorPosition(0)
        elif isinstance(nxt, CellTextEdit):
            tc = nxt.textCursor(); tc.movePosition(QtGui.QTextCursor.Start); nxt.setTextCursor(tc)
            nxt.ensureCursorVisible()
        if isinstance(old_inner, CellTextEdit):
            old_inner.viewport().update()
        else:
            old_inner.update()
        self._layout.activate()

    def update_editor(self):
        if self._layout.count() == 0:
            for v in self.value:
                self._layout.addWidget(self._make_cell(v))


class FlowListStrEditor(BasicEditorFactory):
    klass = _FlowListStrEditor
    max_lines = Int(4)


# -------------------------- Demo --------------------------

if __name__ == "__main__":
    from traits.api import HasTraits, List, Str
    from traitsui.api import Item, View

    class Demo(HasTraits):
        one_line = List(Str, [
            "https://example.com/really/long/path/1/file.ext",
            "A longer text in cell 2 that may not fit the width",
            "",
            "Tail",
        ])
        multi = List(Str, [
            "",
            "Alpha",
            "Bravo long wrapped text that should span multiple lines and then stop at four lines at most.",
            "Charlie",
            "Delta",
            "Echo",
            "Zulu " * 40,
        ])

        traits_view = View(
            HGroup(
                Item("one_line", label="List(Str) — one-line", editor=FlowListStrEditor(max_lines=1), show_label=True),
                Item("multi",    label="List(Str) — wrapped (max=4)", editor=FlowListStrEditor(max_lines=4), show_label=True),
            ),
            resizable=True,
            buttons=["OK"],
            title="FlowListStrEditor — uniform paste: compose-then-split for 1-line & wrapped",
        )

    Demo().configure_traits()
