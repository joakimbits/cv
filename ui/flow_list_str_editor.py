# ui/flow_list_str_editor.py
from __future__ import annotations

import math
from typing import List as TList, Optional, Literal

from traits.api import Int, Bool
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor

from PySide6 import QtWidgets, QtCore, QtGui


# ----------------------- Tiny badge (used by multiline or single-line if desired) -----------------------

class _OverflowBadge(QtWidgets.QWidget):
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

    def sizeHint(self) -> QtCore.QSize:
        fm = QtGui.QFontMetrics(self.font())
        return QtCore.QSize(fm.horizontalAdvance(self._text) + 12, fm.height() + 4)

    def paintEvent(self, _: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        bg = self.palette().color(QtGui.QPalette.Midlight)
        pen = self.palette().color(QtGui.QPalette.Mid)
        p.setPen(pen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 8, 8)
        p.setPen(self.palette().color(QtGui.QPalette.WindowText))
        p.drawText(self.rect().adjusted(6, 2, -6, -2), QtCore.Qt.AlignCenter, self._text)


# ------------------------------ Multi-line Cell ------------------------------

_OverflowCount = Literal["lines", "chars", "none"]

class _Cell(QtWidgets.QTextEdit):
    """Wrapping plain-text cell with capped natural height + optional badge (no layout pings while typing)."""
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

        self._count_mode: _OverflowCount = overflow_count_mode if overflow_count_mode in ("lines", "chars", "none") else "lines"
        self._badge = _OverflowBadge(self) if show_overflow_badge else None
        if self._badge:
            self._badge.hide()

        self.document().documentLayout().documentSizeChanged.connect(self._refresh_overflow_badge)

    def set_column_width(self, width_px: int) -> None:
        width_px = max(1, int(width_px))
        if width_px == self._cached_col_w:
            return
        self._cached_col_w = width_px
        self.document().setTextWidth(float(width_px))
        self._refresh_overflow_badge()

    def _line_h(self) -> float:
        return max(1.0, QtGui.QFontMetricsF(self.font()).lineSpacing())

    def _wrapped_lines(self) -> int:
        return max(1, int(math.ceil(float(self.document().size().height()) / self._line_h())))

    def _extra_lines(self) -> int:
        return max(0, self._wrapped_lines() - self._max_lines)

    def _extra_chars(self) -> int:
        if self._extra_lines() <= 0:
            return 0
        doc = self.document()
        extra = 0
        budget = self._max_lines
        b = doc.begin()
        while b.isValid():
            layout = b.layout()
            lc = layout.lineCount() if layout else 1
            if budget <= 0:
                extra += b.length()
            else:
                if lc > budget:
                    frac = max(0, lc - budget) / max(1, lc)
                    extra += int(b.length() * frac)
                budget -= lc
            b = b.next()
        return max(0, extra)

    def natural_px(self, col_w: int) -> int:
        self.set_column_width(col_w)
        lines = max(self._min_lines, min(self._wrapped_lines(), self._max_lines))
        m = self.contentsMargins()
        return int(lines * self._line_h() + m.top() + m.bottom() + self.frameWidth() * 2 + 2)

    def _badge_text(self) -> str:
        if not self._badge:
            return ""
        if self._count_mode == "none":
            return "…"
        if self._count_mode == "lines":
            n = self._extra_lines()
            return "…" if n <= 0 else f"… {n} more"
        n = self._extra_chars()
        return "…" if n <= 0 else f"… {n} chars"

    def _refresh_overflow_badge(self) -> None:
        if not self._badge:
            return
        if self._extra_lines() <= 0:
            self._badge.hide()
            return
        self._badge.set_text(self._badge_text())
        sz = self._badge.sizeHint()
        cr = self.contentsRect()
        self._badge.setGeometry(cr.right() - sz.width() - 2, cr.bottom() - sz.height() - 2, sz.width(), sz.height())
        self._badge.show()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._refresh_overflow_badge()

    def focusOutEvent(self, ev: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(ev)
        host = self.parent()
        if host is not None and hasattr(host, "_editor_backref"):
            host._editor_backref()._ui_to_model()  # type: ignore[func-returns-value]
        p = self.parentWidget()
        if isinstance(p, QtWidgets.QWidget):
            p.updateGeometry()


# ------------------------------ One-line (elided) Cell ------------------------------

class _ElidedOneLineCell(QtWidgets.QLineEdit):
    """
    Single-line cell. When not focused, shows an ellipsis ('…') inside the text if too wide.
    When focused, behaves like a normal QLineEdit (caret, horizontal scroll).
    """
    def __init__(self, parent=None, *, elide_enabled: bool = True):
        super().__init__(parent)
        self.setFrame(False)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._col_w: int = -1
        self._elide_enabled = bool(elide_enabled)
        self.textChanged.connect(self._maybe_update_elide)
        self.setToolTipDuration(0)  # persistent

    # API parity with multiline cell
    def set_column_width(self, width_px: int) -> None:
        width_px = max(1, int(width_px))
        if width_px == self._col_w:
            return
        self._col_w = width_px
        self._maybe_update_elide()

    def natural_px(self, col_w: int) -> int:
        self.set_column_width(col_w)
        fm = QtGui.QFontMetrics(self.font())
        m = self.contentsMargins()
        return int(fm.lineSpacing() + m.top() + m.bottom() + 2)

    # --- elide logic helpers ---
    def _available_width(self) -> int:
        """
        Width available for drawing text when not focused.
        Use contentsRect (accounts for style/margins), minus tiny padding.
        """
        cr = self.contentsRect()
        return max(1, cr.width() - 4)

    def _maybe_update_elide(self) -> None:
        if not self._elide_enabled:
            self.setToolTip("")
            return
        fm = QtGui.QFontMetrics(self.font())
        needs_elide = fm.horizontalAdvance(self.text()) > self._available_width()
        self.setToolTip(self.text() if needs_elide else "")
        if not self.hasFocus():
            self.update()  # repaint with (or without) elide

    def paintEvent(self, e: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self.hasFocus() or not self._elide_enabled:
            return super().paintEvent(e)

        # Custom paint with elided text
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        p.fillRect(self.rect(), self.palette().brush(QtGui.QPalette.Base))

        fm = QtGui.QFontMetrics(self.font())
        elided = fm.elidedText(self.text(), QtCore.Qt.ElideRight, self._available_width())

        r = self.contentsRect().adjusted(2, 0, -2, 0)
        p.setPen(self.palette().color(QtGui.QPalette.Text))
        p.drawText(r, int(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft), elided)

    def focusInEvent(self, e: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusInEvent(e)
        self.update()  # switch back to native painting while editing

    def focusOutEvent(self, ev: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(ev)
        host = self.parent()
        if host is not None and hasattr(host, "_editor_backref"):
            host._editor_backref()._ui_to_model()  # type: ignore[func-returns-value]
        p = self.parentWidget()
        if isinstance(p, QtWidgets.QWidget):
            p.updateGeometry()
        self._maybe_update_elide()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._maybe_update_elide()


# --------------------------- Newspaper Layout (pure QLayout) ---------------------------

class _NewspaperLayout(QtWidgets.QLayout):
    """Dynamic widths + dynamic column count, greedy top→bottom. Optional list-level overflow indicator."""
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
        self._indicator: Optional[_OverflowBadge] = _OverflowBadge(self.parentWidget()) if show_overflow_indicator else None
        if self._indicator:
            self._indicator.hide()
        self.setSpacing(self._h_spacing)

    # QLayout boilerplate
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
        min_w = self._min_columns * max(self._min_column_width, 160) + (self._min_columns - 1) * self._h_spacing
        w = max(min_w, pw.width()) if isinstance(pw, QtWidgets.QWidget) and pw.width() > 0 else min_w
        return QtCore.QSize(w, 400)

    def minimumSize(self) -> QtCore.QSize:  # noqa: N802
        min_w = self._min_columns * self._min_column_width + (self._min_columns - 1) * self._h_spacing
        return QtCore.QSize(min_w, 48)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        if rect.width() > 0:
            self._compute_layout(rect)

    # helpers
    def _cells(self):
        out = []
        for it in self._items:
            w = it.widget()
            if isinstance(w, (_Cell, _ElidedOneLineCell)):
                out.append(w)
        return out

    def _feasible_max_cols_by_width(self, usable_w: int) -> int:
        if usable_w <= 0:
            return self._min_columns
        for cols in range(self._max_columns, self._min_columns - 1, -1):
            total = cols * self._min_column_width + (cols - 1) * self._h_spacing
            if total <= usable_w:
                return cols
        return self._min_columns

    def _simulate_place_count(self, cols: int, col_w: int, cap_h: int) -> int:
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

    def _compute_layout(self, rect: QtCore.QRect) -> None:
        usable_w = max(1, rect.width())
        cap_h = max(1, rect.height())
        cells = self._cells()
        total_cells = len(cells)

        # Decide column count & width (unchanged)
        feasible_max = self._feasible_max_cols_by_width(usable_w)
        chosen_cols = self._min_columns
        col_w = max(self._min_column_width, (usable_w - (chosen_cols - 1) * self._h_spacing) // chosen_cols)
        for cols in range(self._min_columns, feasible_max + 1):
            col_w = max(self._min_column_width, (usable_w - (cols - 1) * self._h_spacing) // cols)
            fit = self._simulate_place_count(cols, col_w, cap_h)
            chosen_cols = cols
            if fit >= total_cells:
                break

        # Place greedily (full height; no reservation)
        x = rect.x()
        y_top = rect.y()
        i = 0
        last_col_x = x
        last_col_bottom_y = y_top  # track for badge anchor
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
            last_col_bottom_y = y  # bottom after last placed in this column
            x += col_w + self._h_spacing

        leftover = total_cells - i

        # Overlay badge ABOVE the last cell (z-order)
        if self._indicator:
            if leftover > 0:
                self._indicator.set_text(f"…  {leftover} more")
                self._indicator.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                sz = self._indicator.sizeHint()

                # bottom-right inside the last column; overlay without reserving space
                col_right = min(last_col_x + col_w, rect.right())
                ind_x = col_right - sz.width()
                # anchor to min(view bottom, last column bottom)
                anchor_y = min(rect.y() + cap_h, last_col_bottom_y)
                ind_y = min(anchor_y, rect.bottom()) - sz.height()

                # clamp to viewport
                ind_x = max(rect.x(), min(ind_x, rect.right() - sz.width()))
                ind_y = max(rect.y(), min(ind_y, rect.bottom() - sz.height()))

                self._indicator.setGeometry(ind_x, ind_y, sz.width(), sz.height())
                self._indicator.show()
                self._indicator.raise_()  # ensure on top of cells
            else:
                self._indicator.hide()

        # Hide leftovers safely (if any)
        zero = QtCore.QRect(0, 0, 0, 0)
        for j in range(i, len(cells)):
            cells[j].setGeometry(zero)
            cells[j].hide()


# ------------------------- Host (fires real Qt relayouts only) -------------------------

class _FlowHost(QtWidgets.QWidget):
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
    """Newspaper layout editor; supports multiline cells and elided one-line cells."""
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
        self._cells: list[QtWidgets.QWidget] = []
        self._building = False

        self._bind_backref()
        self.update_editor()

    def _bind_backref(self):
        import weakref
        setattr(self.control, "_editor_backref", weakref.ref(self))

    def update_editor(self):
        vals = [str(x) if x is not None else "" for x in (self.value or [])]
        if len(vals) != len(self._cells):
            self._rebuild_fields(vals)
        else:
            for i, c in enumerate(self._cells):
                t = vals[i] if i < len(vals) else ""
                if isinstance(c, QtWidgets.QLineEdit):
                    if c.text() != t:
                        c.blockSignals(True)
                        c.setText(t)
                        c.blockSignals(False)
                elif isinstance(c, QtWidgets.QTextEdit):
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
        single_line = bool(self.factory.single_line)
        single_line_elide = bool(self.factory.single_line_elide)

        for v in (vals or [""]):
            if single_line:
                cell = _ElidedOneLineCell(self.control, elide_enabled=single_line_elide)
                cell.setText(v)
            else:
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

    def _ui_to_model(self):
        if self._building:
            return
        out: TList[str] = []
        for c in self._cells:
            s = c.text() if isinstance(c, QtWidgets.QLineEdit) else c.toPlainText()
            if s.strip():
                out.append(s)
        self.value = out


class FlowListStrEditor(BasicEditorFactory):
    """
    Item('bullets', editor=FlowListStrEditor(
        single_line=True,
        single_line_elide=True,          # ← ellipsis inside the one-line cells
        min_columns=1, max_columns=6,
        min_column_width=140,
        show_overflow_indicator=True,    # list-level "… N more"
        # if multiline:
        min_lines=1, max_lines=6,
        cell_overflow_badge=True,        # per-cell badge for multiline
        cell_overflow_count_lines=True))
    """
    klass = _FlowListEditor

    # one-liner mode
    single_line = Bool(False)
    single_line_elide = Bool(True)

    # list-level column policy
    min_columns = Int(1)
    max_columns = Int(6)
    min_column_width = Int(140)
    show_overflow_indicator = Bool(True)

    # spacing
    h_spacing = Int(12)
    v_spacing = Int(0)

    # multiline bounds + per-cell badge (ignored in single-line)
    min_lines = Int(1)
    max_lines = Int(6)
    cell_overflow_badge = Bool(True)
    cell_overflow_count_lines = Bool(True)
    cell_overflow_count_chars = Bool(False)


# ------------------------------- demo -------------------------------

if __name__ == "__main__":
    from traits.api import HasTraits, List, Str
    from traitsui.api import Item, View, Group

    class Demo(HasTraits):
        bullets = List(Str, [f"Very long one-liner {i} — https://example.com/path/to/resource/{i}/with/some/parameters"
                             for i in range(1, 80)])

        traits_view = View(
            Group(
                Item("bullets", editor=FlowListStrEditor(
                    single_line=True,              # switch False for multiline
                    single_line_elide=True,        # ← in-cell ellipsis
                    min_columns=1, max_columns=6,
                    min_column_width=180,
                    show_overflow_indicator=True,
                    # multiline-only:
                    min_lines=1, max_lines=6,
                    cell_overflow_badge=True,
                    cell_overflow_count_lines=True,
                )),
                show_border=False,
            ),
            resizable=True, buttons=["OK"]
        )

    Demo().configure_traits()
