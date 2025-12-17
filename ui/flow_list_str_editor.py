# ui/flow_list_str_editor.py
from __future__ import annotations

import math
from typing import List as TList, Optional, Literal

from traits.api import Int, Bool
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor

from PySide6 import QtWidgets, QtCore, QtGui


# ----------------------- Overflow badge (per-cell) -----------------------

class _OverflowBadge(QtWidgets.QWidget):
    """Small rounded pill with '…' or '… N more'. Pure paint for low overhead."""
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._text = "…"
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self.update()

    def sizeHint(self) -> QtCore.QSize:  # small pill
        fm = QtGui.QFontMetrics(self.font())
        w = fm.horizontalAdvance(self._text) + 12
        h = fm.height() + 4
        return QtCore.QSize(w, h)

    def paintEvent(self, ev: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = self.rect()
        # background
        bg = self.palette().color(QtGui.QPalette.ColorRole.Midlight)
        pen = self.palette().color(QtGui.QPalette.ColorRole.Mid)
        p.setPen(pen)
        p.setBrush(bg)
        p.drawRoundedRect(r.adjusted(0, 0, -1, -1), 8, 8)
        # text
        p.setPen(self.palette().color(QtGui.QPalette.ColorRole.WindowText))
        p.drawText(r.adjusted(6, 2, -6, -2), QtCore.Qt.AlignCenter, self._text)


# ------------------------------ Cell ------------------------------

_OverflowCount = Literal["lines", "chars", "none"]

class _Cell(QtWidgets.QTextEdit):
    """
    Wrapping plain-text cell with capped natural height.
    Optional per-cell overflow badge when text exceeds max_lines.
    """
    def __init__(
        self,
        parent=None,
        *,
        min_lines: int = 1,
        max_lines: int = 6,
        show_overflow_badge: bool = True,
        overflow_count_mode: _OverflowCount = "lines",
    ):
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
        self._cached_col_w: int = -1

        self._show_badge = bool(show_overflow_badge)
        self._count_mode: _OverflowCount = overflow_count_mode if overflow_count_mode in ("lines", "chars", "none") else "lines"
        self._badge = _OverflowBadge(self) if self._show_badge else None
        if self._badge:
            self._badge.hide()

        # Update only the badge on content wrap changes; do NOT poke outer layout.
        self.document().documentLayout().documentSizeChanged.connect(self._refresh_overflow_badge)

    # ---- measuring helpers ----

    def set_column_width(self, width_px: int) -> None:
        width_px = max(1, int(width_px))
        if width_px == self._cached_col_w:
            return
        self._cached_col_w = width_px
        self.document().setTextWidth(float(width_px))
        # badge may need to move/retitle
        self._refresh_overflow_badge()

    def _line_h(self) -> float:
        fm = QtGui.QFontMetricsF(self.font())
        return max(1.0, fm.lineSpacing())

    def _wrapped_lines(self) -> int:
        h = float(self.document().size().height())
        return max(1, int(math.ceil(h / self._line_h())))

    def _extra_lines(self) -> int:
        return max(0, self._wrapped_lines() - self._max_lines)

    def _extra_chars(self) -> int:
        # Approximate: characters beyond last visible block
        if self._extra_lines() <= 0:
            return 0
        doc = self.document()
        # count chars in blocks beyond max_lines (rough, fast)
        extra = 0
        line_budget = self._max_lines
        b = doc.begin()
        while b.isValid():
            layout = b.layout()
            line_count = layout.lineCount() if layout else 1
            if line_budget <= 0:
                extra += b.length()  # includes '\n'
            else:
                if line_count > line_budget:
                    # part of this block overflows
                    # crude estimate: proportional split
                    frac = max(0, line_count - line_budget) / max(1, line_count)
                    extra += int(b.length() * frac)
                line_budget -= line_count
            b = b.next()
        return max(0, extra)

    def natural_px(self, col_w: int) -> int:
        self.set_column_width(col_w)
        lines = max(self._min_lines, min(self._wrapped_lines(), self._max_lines))
        m = self.contentsMargins()
        frame = self.frameWidth()
        return int(lines * self._line_h() + m.top() + m.bottom() + frame * 2 + 2)

    # ---- overflow badge ----

    def _badge_text(self) -> str:
        if self._count_mode == "none":
            return "…"
        if self._count_mode == "lines":
            n = self._extra_lines()
            return "…" if n <= 0 else f"… {n} more"
        # chars
        n = self._extra_chars()
        return "…" if n <= 0 else f"… {n} chars"

    def _refresh_overflow_badge(self) -> None:
        if not self._badge:
            return
        overflow = self._extra_lines() > 0
        if not overflow:
            self._badge.hide()
            return
        self._badge.set_text(self._badge_text())
        sz = self._badge.sizeHint()
        cr = self.contentsRect()
        x = cr.right() - sz.width() - 2
        y = cr.bottom() - sz.height() - 2
        self._badge.setGeometry(QtCore.QRect(x, y, sz.width(), sz.height()))
        self._badge.show()

    def resizeEvent(self, ev: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self._refresh_overflow_badge()

    # push value on focus-out (quiet; outer layout relayout handled by host)
    def focusOutEvent(self, ev: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(ev)
        host = self.parent()
        if host is not None and hasattr(host, "_editor_backref"):
            host._editor_backref()._ui_to_model()  # type: ignore[func-returns-value]
        p = self.parentWidget()
        if isinstance(p, QtWidgets.QWidget):
            p.updateGeometry()


# ----------------------- Overflow Indicator (passive) -----------------------

class _OverflowIndicator(QtWidgets.QLabel):
    """Small passive indicator placed by the layout when not all cells fit."""
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("…", parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setStyleSheet("color: palette(window-text); padding: 2px 6px; border-radius: 8px; "
                           "background: palette(midlight);")
        f = self.font()
        f.setPointSize(max(8, f.pointSize() - 1))
        self.setFont(f)

    def set_count(self, n: int) -> None:
        self.setText(f"…  {n} more")


# --------------------------- Pure QLayout (auto-growing columns) ---------------------------

class _NewspaperLayout(QtWidgets.QLayout):
    """Dynamic widths + dynamic columns. Grows columns until all cells fit, else shows overflow indicator."""
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget],
        *,
        min_columns: int,
        max_columns: int,
        h_spacing: int,
        v_spacing: int,
        min_column_width: int = 140,
        show_overflow_indicator: bool = True,
    ):
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self._min_columns = max(1, int(min_columns))
        self._max_columns = max(self._min_columns, int(max_columns))
        self._h_spacing = int(h_spacing)
        self._v_spacing = int(v_spacing)
        self._min_column_width = max(40, int(min_column_width))
        self._indicator: Optional[_OverflowIndicator] = None
        self._show_indicator = bool(show_overflow_indicator)
        self.setSpacing(self._h_spacing)

    # ---- QLayout API ----

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:  # noqa: N802
        return len(self._items) + (1 if self._indicator else 0)

    def itemAt(self, index: int) -> Optional[QtWidgets.QLayoutItem]:  # noqa: N802
        # We don't expose indicator as an item; it is positioned manually.
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> Optional[QtWidgets.QLayoutItem]:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        pw = self.parentWidget()
        min_w = self._min_columns * max(self._min_column_width, 160) + (self._min_columns - 1) * self._h_spacing
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

    def _cells(self) -> list[_Cell]:
        out: list[_Cell] = []
        for it in self._items:
            w = it.widget()
            if isinstance(w, _Cell):
                out.append(w)
        return out

    def _feasible_max_cols_by_width(self, usable_w: int) -> int:
        """Upper bound on columns so that each col >= min_column_width and gaps fit."""
        if usable_w <= 0:
            return self._min_columns
        for cols in range(self._max_columns, self._min_columns - 1, -1):
            total = cols * self._min_column_width + (cols - 1) * self._h_spacing
            if total <= usable_w:
                return cols
        return self._min_columns

    def _simulate_place_count(self, cols: int, col_w: int, cap_h: int) -> int:
        """How many fit greedily across `cols` with column width `col_w` and height cap."""
        cells = self._cells()
        placed = 0
        col = 0
        used = 0
        i = 0
        while i < len(cells) and col < cols:
            c = cells[i]
            h = c.natural_px(col_w)
            if used > 0 and used + h > cap_h:
                col += 1
                used = 0
                continue
            used += h
            placed += 1
            i += 1
            if i < len(cells) and used + self._v_spacing <= cap_h:
                used += self._v_spacing
            else:
                col += 1
                used = 0
        return placed

    def _ensure_indicator(self) -> _OverflowIndicator:
        if self._indicator is None:
            self._indicator = _OverflowIndicator(self.parentWidget())
        return self._indicator

    def _hide_indicator(self) -> None:
        if self._indicator is not None:
            self._indicator.hide()

    def _compute_layout(self, rect: QtCore.QRect) -> None:
        usable_w = max(1, rect.width())
        cap_h = max(1, rect.height())
        cells = self._cells()
        total_cells = len(cells)

        # Decide column count and per-column width (dynamic widths preserved).
        feasible_max = self._feasible_max_cols_by_width(usable_w)
        chosen_cols = self._min_columns
        col_w = max(self._min_column_width, (usable_w - (chosen_cols - 1) * self._h_spacing) // chosen_cols)
        for cols in range(self._min_columns, feasible_max + 1):
            col_w = max(self._min_column_width, (usable_w - (cols - 1) * self._h_spacing) // cols)
            fit = self._simulate_place_count(cols, col_w, cap_h)
            chosen_cols = cols
            if fit >= total_cells:
                break  # first cols that fits all items

        # Place greedily using chosen_cols/col_w
        x = rect.x()
        y_top = rect.y()
        i = 0
        last_col_x = x
        for _col in range(chosen_cols):
            y = y_top
            used = 0
            while i < len(cells):
                c = cells[i]
                h = c.natural_px(col_w)
                if used > 0 and (y + h - y_top) > cap_h:
                    break
                c.setGeometry(QtCore.QRect(x, y, col_w, h))
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
            last_col_x = x
            x += col_w + self._h_spacing

        # Leftovers?
        leftover = total_cells - i
        if leftover > 0 and self._show_indicator:
            # Place a small "... N more" at the bottom-right of the last visible column, inside the cap.
            ind = self._ensure_indicator()
            ind.set_count(leftover)
            ind_size = ind.sizeHint()
            ind_x = min(last_col_x + col_w - ind_size.width(), rect.right() - ind_size.width())
            ind_y = min(y_top + cap_h - ind_size.height(), rect.bottom() - ind_size.height())
            ind.setGeometry(QtCore.QRect(ind_x, ind_y, ind_size.width(), ind_size.height()))
            ind.show()
        else:
            self._hide_indicator()

        # Hide stale leftovers (no ghosting)
        zero = QtCore.QRect(0, 0, 0, 0)
        for j in range(i, len(cells)):
            cells[j].setGeometry(zero)
            cells[j].hide()


# ------------------------- Host widget: trigger real Qt relayouts -------------------------

class _FlowHost(QtWidgets.QWidget):
    """Container that requests a layout pass on Qt events (no timers, no queued invokes)."""
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
    """Editable List(Str) with dynamic widths + dynamic column count, overflow indicator when needed."""
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
            show_overflow_indicator=bool(self.factory.show_overflow_indicator),
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

        while self._layout.count():
            it = self._layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)

        for c in self._cells:
            c.deleteLater()
        self._cells.clear()

        min_l = max(1, int(self.factory.min_lines))
        max_l = max(min_l, int(self.factory.max_lines))

        for v in (vals or [""]):
            cell = _Cell(
                self.control,
                min_lines=min_l,
                max_lines=max_l,
                show_overflow_badge=bool(self.factory.cell_overflow_badge),
                overflow_count_mode=("lines" if self.factory.cell_overflow_count_lines
                                     else "chars" if self.factory.cell_overflow_count_chars
                                     else "none"),
            )
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
            min_columns=1, max_columns=6, min_column_width=140,
            h_spacing=12, v_spacing=0,
            # list-level overflow indicator (already implemented previously)
            show_overflow_indicator=True,
            # per-cell overflow badge:
            cell_overflow_badge=True,
            cell_overflow_count_lines=True,   # or set cell_overflow_count_chars=True
            min_lines=1, max_lines=6))
    """
    klass = _FlowListEditor

    # list-level column policy (as before)
    min_columns = Int(1)
    max_columns = Int(6)
    min_column_width = Int(140)
    h_spacing = Int(12)
    v_spacing = Int(0)
    show_overflow_indicator = Bool(True)

    # per-cell line bounds
    min_lines = Int(1)
    max_lines = Int(6)

    # per-cell overflow badge
    cell_overflow_badge = Bool(True)
    cell_overflow_count_lines = Bool(True)   # mutually exclusive with chars
    cell_overflow_count_chars = Bool(False)


# ------------------------------- demo -------------------------------

if __name__ == "__main__":
    from traits.api import HasTraits, List, Str
    from traitsui.api import Item, View, Group

    class Demo(HasTraits):
        bullets = List(Str, [f"Item {i}: A longer string that wraps a few times" for i in range(1, 180)])

        traits_view = View(
            Group(
                Item("bullets", editor=FlowListStrEditor(
                    min_columns=1, max_columns=6,
                    min_column_width=140,
                    show_overflow_indicator=True,
                    min_lines=1, max_lines=6,
                    h_spacing=12, v_spacing=0,
                )),
                show_border=False,
            ),
            resizable=True, buttons=["OK"]
        )

    Demo().configure_traits()
