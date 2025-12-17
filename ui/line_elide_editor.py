# ui/line_elide_editor.py
from __future__ import annotations
from typing import Literal

from traits.api import HasTraits, Str, Bool
from traitsui.api import Item, View, Group, BasicEditorFactory
from traitsui.qt.editor import Editor

from PySide6 import QtCore, QtGui, QtWidgets

# ---------------- attachable QLineEdit elide overlay ----------------

ElideMode = Literal["end", "middle"]

class _ElideOverlay(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setVisible(False)
        self.setStyleSheet("border:0; padding:0;")

    def paintEvent(self, _: QtGui.QPaintEvent) -> None:  # solid background to hide caret behind
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        pal = self.parentWidget().palette()
        p.fillRect(self.rect(), pal.brush(QtGui.QPalette.Base))
        p.setPen(pal.color(QtGui.QPalette.Text))
        p.drawText(self.rect().adjusted(2, 0, -2, 0),
                   int(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft),
                   self.text())

class _LineEditElideCtl(QtCore.QObject):
    def __init__(self, le: QtWidgets.QLineEdit, mode: ElideMode = "end", select_all_on_focus: bool = False):
        super().__init__(le)
        self._le = le
        self._mode = mode
        self._select_all = bool(select_all_on_focus)
        self._overlay = _ElideOverlay(le)
        le.installEventFilter(self)
        le.textChanged.connect(self._update)
        self._update()

    def set_mode(self, mode: ElideMode) -> None:
        self._mode = mode
        self._update()

    def eventFilter(self, obj, ev):  # noqa: N802
        if obj is self._le:
            t = ev.type()
            if t in (QtCore.QEvent.Resize, QtCore.QEvent.Show, QtCore.QEvent.PaletteChange):
                self._reposition(); self._update()
            elif t == QtCore.QEvent.FocusIn:
                if self._select_all:
                    QtCore.QTimer.singleShot(0, self._le.selectAll)
                self._overlay.hide()
            elif t == QtCore.QEvent.FocusOut:
                self._update()
        return super().eventFilter(obj, ev)

    def _avail_w(self) -> int:
        return max(1, self._le.contentsRect().width() - 4)

    def _elided(self, text: str) -> str:
        fm = QtGui.QFontMetrics(self._le.font())
        mode = QtCore.Qt.ElideMiddle if self._mode == "middle" else QtCore.Qt.ElideRight
        return fm.elidedText(text, mode, self._avail_w())

    def _reposition(self) -> None:
        self._overlay.setGeometry(self._le.contentsRect())

    def _update(self) -> None:
        self._reposition()
        if self._le.hasFocus():
            self._overlay.hide(); self._le.setToolTip(""); return
        text = self._le.text()
        fm = QtGui.QFontMetrics(self._le.font())
        needs = fm.horizontalAdvance(text) > self._avail_w()
        if needs:
            self._overlay.setText(self._elided(text))
            self._overlay.show(); self._overlay.raise_()
            self._le.setToolTip(text)
        else:
            self._overlay.hide(); self._le.setToolTip("")

def attach_lineedit_elide(line_edit: QtWidgets.QLineEdit,
                          mode: ElideMode = "end",
                          select_all_on_focus: bool = False) -> _LineEditElideCtl:
    return _LineEditElideCtl(line_edit, mode=mode, select_all_on_focus=select_all_on_focus)

# ---------------- TraitsUI editor: LineElideEditor ----------------

class _LineElideEditor(Editor):
    def init(self, parent):
        wparent = parent if isinstance(parent, QtWidgets.QWidget) else None
        le = QtWidgets.QLineEdit(wparent)
        le.setText(str(self.value or ""))
        self.control = le
        mode = "middle" if bool(getattr(self.factory, "elide_middle", False)) else "end"
        self._ctl = attach_lineedit_elide(le, mode=mode, select_all_on_focus=bool(getattr(self.factory, "select_all_on_focus", False)))

    def update_editor(self):
        s = str(self.value or "")
        if self.control.text() != s:
            self.control.blockSignals(True)
            self.control.setText(s)
            self.control.blockSignals(False)

    def _ui_to_model(self):
        self.value = self.control.text()

class LineElideEditor(BasicEditorFactory):
    """Drop-in single-line Str editor with in-field ellipsis."""
    klass = _LineElideEditor
    elide_middle = Bool(False)
    select_all_on_focus = Bool(False)

# ---------------- Demo (TraitsUI) ----------------

if __name__ == "__main__":
    from auto_height_text_editor import AutoHeightTextEditor

    class Demo(HasTraits):
        title = Str("A very long plain title that should elide at the end when not focused")
        url = Str("https://example.com/this/is/a/very/long/path/with/lots/of/segments/index.html?with=params&and=more")
        notes = Str("\n".join([f"Line {i}" for i in range(15)]))

        traits_view = View(
            Group(
                Item("title", editor=LineElideEditor(elide_middle=False, select_all_on_focus=True), label="Title"),
                Item("url", editor=LineElideEditor(elide_middle=True, select_all_on_focus=True), label="URL"),
                Item("notes", editor=AutoHeightTextEditor(), label="Notes (auto-height + badge)"),
                show_border=False,
            ),
            resizable=True, buttons=["OK"], title="TraitsUI — Single-line elide + Notes badge"
        )

    Demo().configure_traits()
