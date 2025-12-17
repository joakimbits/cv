# auto_height_text_editor.py
from __future__ import annotations
import math, weakref
from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor
from PySide6 import QtWidgets, QtGui, QtCore

from ui.overflow_badge_helper import attach_overflow_badge


class _ResizeWatcher(QtCore.QObject):
    """Forwards Resize events to the editor's _resize_to_content()."""
    def __init__(self, editor: "._AutoHeightTextEditor"):
        super().__init__()
        self._eref = weakref.ref(editor)

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if event.type() == QtCore.QEvent.Resize:
            ed = self._eref()
            if ed is not None:
                QtCore.QTimer.singleShot(0, ed._resize_to_content)  # defer until layout settles
        return False  # don't eat the event

class _AutoHeightTextEditor(Editor):
    """Qt editor that auto-resizes to wrapped content; supports Str and List(Str)."""

    def init(self, parent):
        # parent may be a QLayout or a QWidget – either way, DO NOT add to layout here.
        if isinstance(parent, QtWidgets.QWidget):
            te = QtWidgets.QTextEdit(parent)  # ok to pass QWidget as parent
        else:
            te = QtWidgets.QTextEdit()  # if it's a QLayout, create without parent

        te.setAcceptRichText(False)
        te.setFrameShape(QtWidgets.QFrame.NoFrame)
        te.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        te.setTabChangesFocus(True)
        te.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        te.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        te.textChanged.connect(self._on_text_changed)

        # wrap/resize observers (keep references!)
        self._watcher = _ResizeWatcher(self)
        te.viewport().installEventFilter(self._watcher)
        te.document().documentLayout().documentSizeChanged.connect(
            lambda *_: self._resize_to_content()
        )

        self.control = te  # <- let TraitsUI place it next to the label
        self._overflow_badge_ctl = attach_overflow_badge(self.control, mode="lines")
        self._list_mode = isinstance(self.value, (list, tuple))

        self.update_editor()
        self._resize_to_content()

    def update_editor(self):
        v = self.value
        text = ("\n".join("" if s is None else str(s) for s in (v or []))
                if self._list_mode else ("" if v is None else str(v)))
        if self.control.toPlainText() != text:
            self.control.blockSignals(True)
            self.control.setPlainText(text)
            self.control.blockSignals(False)
            self._resize_to_content()

    def _on_text_changed(self):
        text = self.control.toPlainText()
        self.value = text.splitlines() if self._list_mode else text
        self._resize_to_content()

    def _wrapped_line_count(self) -> int:
        doc = self.control.document()
        doc.setTextWidth(self.control.viewport().width())
        line_h = self.control.fontMetrics().lineSpacing() or 1
        h = doc.size().height()
        return max(1, int(math.ceil(h / line_h)))

    def _resize_to_content(self):
        lines = self._wrapped_line_count()
        lines = max(self.factory.min_lines, min(lines, self.factory.max_lines))
        fm = self.control.fontMetrics()
        line_h = fm.lineSpacing()
        m = self.control.contentsMargins()
        frame = self.control.frameWidth() if hasattr(self.control, "frameWidth") else 0
        px = int(lines * line_h + m.top() + m.bottom() + frame * 2 + 2)  # +2 to avoid clipping
        # Why fixed min/max: prevents layout jitter
        self.control.setMinimumHeight(px)
        self.control.setMaximumHeight(px)

class AutoHeightTextEditor(BasicEditorFactory):
    klass = _AutoHeightTextEditor
    min_lines = Int(1)
    max_lines = Int(12)
