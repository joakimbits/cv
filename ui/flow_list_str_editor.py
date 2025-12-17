# ui/flow_list_str_editor.py
from __future__ import annotations

import math
from typing import List as TList, Optional

from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor

from PySide6 import QtWidgets, QtCore, QtGui


# ------------------------------ Cell ------------------------------

class _Cell(QtWidgets.QTextEdit):
    """Wrapping plain-text cell with capped natural (wrapped) height. Quiet while typing."""
    def __init__(self, parent=None, *, min_lines: int = 1, max_lines: int = 6):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self._min_lines = max(1, int(min_lines))
        self._max_lines = max(self._min_lines, int(max_lines))
        self._cached_col_w: int = -1  # avoid redundant setTextWidth

    def set_column_width(self, width_px: int) -> None:
        width_px = max(1, int(width_px))
        if width_px == self._cached_col_w:
            return  # avoid documentSizeChanged churn
        self._cached_col_w = width_px
        self.document().setTextWidth(float(width_px))

    def _line_h(self) -> float:
        fm = QtGui.QFontMetricsF(self.font())
        return max(1.0, fm.lineSpacing())

    def _wrapped_lines(self) -> int:
        h = float(self.document().size().height())
        return max(1, int(math.ceil(h / self._line_h())))

    def natural_px(self, col_w: int) -> int:
        # Ensure document width reflects the column (cached)
        self.set_column_width(col_w)
        lines = max(self._min_lines, min(self._wrapped_lines(), self._max_lines))
        m = self.contentsMargins()
        frame = self.frameWidth()
        return int(lines * self._line_h() + m.top() + m.bottom() + frame * 2 + 2)

    def focusOutEvent(self, ev: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(ev)
        # push value on focus-out (quiet)
        host = self.parent()
        if host is not None and hasattr(host, "_editor_backref"):
            host._editor_backref()._ui_to_model()  # type: ignore[func-returns-value]
        # editing may change height; ask for a relayout
        p = self.parentWidget()
        if isinstance(p, QtWidgets.QWidget):
            p.updateGeometry()


# --------------------------- Pure QLayout with auto-growing columns ---------------------------

class _NewspaperLayout(QtWidgets.QLayout):
    """Auto-growing newspaper columns: start at min_columns, grow until all cells fit (subject to min_column_width & max_columns)."""
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget],
        *,
        min_columns: int,
        max_columns: int,
        h_spacing: int,
        v_spacing: int,
        min_column_width: int = 120,
        per_col_guess_min_px: int = 200,
    ):
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self._min_columns = max(1, int(min_columns))
        self._max_columns = max(self._min_columns, int(max_columns))
        self._h_spacing = int(h_spacing)
        self._v_spacing = int(v_spacing)
        self._min_column_width = max(40, int(min_column_width))
        self._per_col_guess_min_px = int(per_col_guess_min_px)
        self.setSpacing(self._h_spacing)

    # ---- QLayout API ----

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

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        pw = self.parentWidget()
        min_w = self._min_columns * max(self._per_col_guess_min_px, self._min_column_width) + (self._min_columns - 1) * self._h_spacing
        w = max(min_w, pw.width()) if isinstance(pw, QtWidgets.QWidget) and pw.width() > 0 else min_w
        return QtCore.QSize(w, 400)

    def minimumSize(self) -> QtCore.QSize:  # noqa: N802
        min_w = self._min_columns * self._min_column_width + (self._min_columns - 1) * self._h_spacing
        return QtCore.QSize(min_w, 48)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        if rect.width() <= 0:
            return
        self._compute_layout(rect)

    # ---- core placement ----

    def _usable_and_max_cols(self, usable_w: int) -> int:
        """Maximum columns allowed by width and min_column_width."""
        if usable_w <= 0:
            return self._min_columns
        # cols*(min_w) + (cols-1)*h_spacing <= usable_w
        # Try from max_columns downward to find a feasible cap.
        for cols in range(self._max_columns, self._min_columns - 1, -1):
            total = cols * self._min_column_width + (cols - 1) * self._h_spacing
            if total <= usable_w:
                return cols
        return self._min_columns

    def _simulate_place_count(self, cols: int, col_w: int, cap_h: int) -> int:
        """Return how many cells fit across cols, greedily, given col width and cap height."""
        cells: list[_Cell] = []
        for it in self._items:
            w = it.widget()
            if isinstance(w, _Cell):
                cells.append(w)
        placed = 0
        y_used = [0] * cols
        col = 0
        i = 0
        while i < len(cells) and col < cols:
            c = cells[i]
            h = c.natural_px(col_w)
            # start new column if this one can't fit any more
            if y_used[col] > 0 and y_used[col] + h > cap_h:
                col += 1
                continue
            # place
            y_used[col] += h
            placed += 1
            i += 1
            if i < len(cells) and y_used[col] + self._v_spacing <= cap_h:
                y_used[col] += self._v_spacing
            else:
                # next cell won't fit due to spacing; move to next column
                if i < len(cells):
                    col += 1
        return placed

    def _compute_layout(self, rect: QtCore.QRect) -> None:
        usable_w = max(1, rect.width())
        cap_h = max(1, rect.height())

        # Determine feasible upper bound on columns due to width + min_column_width
        feasible_max = self._usable_and_max_cols(usable_w)
        # Start at min_columns and grow until all fit, but never exceed feasible_max
        chosen_cols = self._min_columns
        chosen_col_w = max(self._min_column_width, (usable_w - (chosen_cols - 1) * self._h_spacing) // chosen_cols)

        total_cells = sum(1 for it in self._items if isinstance(it.widget(), _Cell))
        for cols in range(self._min_columns, feasible_max + 1):
            col_w = max(self._min_column_width, (usable_w - (cols - 1) * self._h_spacing) // cols)
            fit = self._simulate_place_count(cols, col_w, cap_h)
            chosen_cols, chosen_col_w = cols, col_w
            if fit >= total_cells:
                break  # earliest cols that fit everything

        # Collect cells
        cells: list[_Cell] = []
        for it in self._items:
            w = it.widget()
            if isinstance(w, _Cell):
                cells.append(w)

        # Place greedily using chosen_cols/col_w
        x = rect.x()
        y_top = rect.y()
        i = 0
        for col in range(chosen_cols):
            y = y_top
            used = 0
            while i < len(cells):
                c = cells[i]
                h = c.natural_px(chosen_col_w)
                if used > 0 and (y + h - y_top) > cap_h:
                    break
                c.setGeometry(QtCore.QRect(x, y, chosen_col_w, h))
                c.show()
                y += h
                used += h
                i += 1
                if i < len(cells):
                    if (y - y_top) + self._v_spacing <= cap_h:
                        y += self._v_spacing
                        used += self._v_spacing
                    else:
                        break
            x += chosen_col_w + self._h_spacing

        # Hide leftovers (should be none if we found a fitting cols)
        zero = QtCore.QRect(0, 0, 0, 0)
        for j in range(i, len(cells)):
            cells[j].setGeometry(zero)
            cells[j].hide()


# ------------------------- Host widget: triggers true Qt relayouts -------------------------

class _FlowHost(QtWidgets.QWidget):
    """Container that requests a layout pass on Qt events (no timers)."""
    def event(self, e: QtCore.QEvent) -> bool:  # noqa: N802
        if e.type() == QtCore.QEvent.LayoutRequest:
            lay = self.layout()
            if isinstance(lay, QtWidgets.QLayout):
                lay.invalidate()
        return super().event(e)

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(e)
        lay = self.layout()
        if isinstance(lay, QtWidgets.QLayout):
            lay.invalidate()


# ------------------------------- Editor -------------------------------

class _FlowListEditor(Editor):
    """Editable List(Str), auto-growing columns until all cells fit. Pure QLayout."""
    def init(self, parent):
        host_parent = parent if isinstance(parent, QtWidgets.QWidget) else None

        host = _FlowHost(host_parent)
        host.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        layout = _NewspaperLayout(
            host,
            min_columns=int(self.factory.min_columns),
            max_columns=int(self.factory.max_columns),
            h_spacing=int(self.factory.h_spacing),
            v_spacing=int(self.factory.v_spacing),
            min_column_width=int(self.factory.min_column_width),
        )
        host.setLayout(layout)

        self.control = host
        self._layout = layout
        self._cells: list[_Cell] = []
        self._building = False

        self._bind_backref()
        self.update_editor()

    def _bind_backref(self):
        import weakref
        setattr(self.control, "_editor_backref", weakref.ref(self))

    # -------------------- model -> ui --------------------

    def update_editor(self):
        vals = [str(x) if x is not None else "" for x in (self.value or [])]
        if len(vals) != len(self._cells):
            self._rebuild_fields(vals)
        else:
            for i, c in enumerate(self._cells):
                t = vals[i] if i < len(vals) else ""
                if c.toPlainText() != t:
                    c.blockSignals(True)
                    c.setPlainText(t)
                    c.blockSignals(False)
        self._layout.invalidate()

    def _rebuild_fields(self, vals: TList[str]):
        self._building = True

        # clear layout items
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        for c in self._cells:
            c.deleteLater()
        self._cells.clear()

        min_l = max(1, int(self.factory.min_lines))
        max_l = max(min_l, int(self.factory.max_lines))
        for v in (vals or [""]):
            cell = _Cell(self.control, min_lines=min_l, max_lines=max_l)
            cell.setPlainText(v)
            self._cells.append(cell)
            self._layout.addWidget(cell)

        self._building = False

    # --------------------- ui -> model -------------------

    def _ui_to_model(self):
        if self._building:
            return
        self.value = [c.toPlainText() for c in self._cells if c.toPlainText().strip() != ""]


class FlowListStrEditor(BasicEditorFactory):
    """
    Use on List(Str):
        Item('bullets', editor=FlowListStrEditor(
            min_columns=1, max_columns=6,
            min_column_width=140,
            min_lines=1, max_lines=6,
            h_spacing=12, v_spacing=0))
    """
    klass = _FlowListEditor

    # column policy
    min_columns = Int(1)
    max_columns = Int(6)
    min_column_width = Int(140)  # prevents columns from getting too narrow

    # spacing
    h_spacing = Int(12)
    v_spacing = Int(0)

    # per-cell line bounds
    min_lines = Int(1)
    max_lines = Int(6)


# ------------------------------- demo -------------------------------

if __name__ == "__main__":
    from traits.api import HasTraits, List, Str
    from traitsui.api import Item, View, Group

    class Demo(HasTraits):
        bullets = List(Str, [f"Item {i}: A longer string that wraps a few times" for i in range(1, 120)])

        traits_view = View(
            Group(
                Item("bullets", editor=FlowListStrEditor(
                    min_columns=1, max_columns=6,
                    min_column_width=140,
                    min_lines=1, max_lines=6,
                    h_spacing=12, v_spacing=0,
                )),
                show_border=False,
            ),
            resizable=True, buttons=["OK"]
        )

    Demo().configure_traits()
