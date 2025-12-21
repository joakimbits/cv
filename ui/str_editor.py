# ui/str_editor.py
import math
from PySide6 import QtCore, QtGui, QtWidgets
from traits.api import Int
from traitsui.basic_editor_factory import BasicEditorFactory
from traitsui.qt.editor import Editor

from ui.elide import attach_line_elide
from ui.auto_height import HeightSizer
from ui.badge import OverflowBadgeCtl, count_wrapped_lines

class _LineStr(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFrame(False)
    def natural_px(self, _w: int) -> int:
        fm = QtGui.QFontMetricsF(self.font()); lh = fm.lineSpacing() or 1.0
        m = self.contentsMargins(); return int(math.ceil(lh + m.top() + m.bottom()))

class _WrapStr(QtWidgets.QTextEdit):
    def __init__(self, parent=None, *, max_lines: int = 4):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self._max = max(1, int(max_lines))
        self.document().setDocumentMargin(0)
    def natural_px(self, col_w: int) -> int:
        doc = self.document(); doc.setTextWidth(float(max(1, int(col_w))))
        fm = QtGui.QFontMetricsF(self.font()); lh = fm.lineSpacing() or 1.0
        lines = min(count_wrapped_lines(doc), self._max)
        m = self.contentsMargins(); border = m.top() + m.bottom() + self.frameWidth() * 2
        return int(math.ceil(lines * lh + border))

class _StrEditor(Editor):
    def init(self, parent):
        host = QtWidgets.QWidget(parent if isinstance(parent, QtWidgets.QWidget) else None)
        lay = QtWidgets.QVBoxLayout(host); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        if int(self.factory.max_lines) == 1:
            w = _LineStr(host); w.setText(self.value or "")
            sp = w.sizePolicy(); sp.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed); w.setSizePolicy(sp)
            self._elide = attach_line_elide(w)
            w.textEdited.connect(lambda *_: self._set_line(w))
        else:
            w = _WrapStr(host, max_lines=int(self.factory.max_lines)); w.setPlainText(self.value or "")
            sp = w.sizePolicy(); sp.setVerticalPolicy(QtWidgets.QSizePolicy.Fixed); w.setSizePolicy(sp)
            self._badge = OverflowBadgeCtl(w, max_lines=int(self.factory.max_lines))
            w.textChanged.connect(lambda *_: self._set_wrap(w))

        lay.addWidget(w)
        self._sizer = HeightSizer(host, w)
        self._w = w
        self.control = host

    def _set_line(self, w: QtWidgets.QLineEdit):
        self.value = w.text(); self._sizer.sync()

    def _set_wrap(self, w: QtWidgets.QTextEdit):
        self.value = w.toPlainText(); self._sizer.sync()

    def update_editor(self):
        if isinstance(self._w, _LineStr):
            blk = self._w.blockSignals(True); self._w.setText(self.value or ""); self._w.blockSignals(blk)
        else:
            self._w.blockSignals(True); self._w.setPlainText(self.value or ""); self._w.blockSignals(False)
        self._sizer.sync()

class StrEditor(BasicEditorFactory):
    klass = _StrEditor
    max_lines = Int(4)

# ---- demo ----
if __name__ == "__main__":
    from traits.api import HasTraits, Str
    from traitsui.api import Item, View
    class Demo(HasTraits):
        line_short = Str("Short line")
        line_long  = Str("This is a really long line of plain text that should elide when unfocused.")
        url_short  = Str("https://example.com")
        url_long   = Str("https://example.com/really/long/path/with/many/segments/and/a/file.html?with=query&and=more")
        wrap_short = Str("Short paragraph that fits.")
        wrap_long  = Str("This is a much longer paragraph intended to wrap across multiple lines in the editor. "
                         "It should grow with content up to max_lines and stop there.")
        traits_view = View(
            Item("line_short", label="Line (short)",       editor=StrEditor(max_lines=1), show_label=True),
            Item("line_long",  label="Line (too long)",    editor=StrEditor(max_lines=1), show_label=True),
            Item("url_short",  label="URL (short)",        editor=StrEditor(max_lines=1), show_label=True),
            Item("url_long",   label="URL (too long)",     editor=StrEditor(max_lines=1), show_label=True),
            Item("wrap_short", label="Wrapped (short)",    editor=StrEditor(max_lines=4), show_label=True),
            Item("wrap_long",  label="Wrapped (too long)", editor=StrEditor(max_lines=4), show_label=True),
            resizable=True, buttons=["OK"], title="StrEditor – modular integration",
        )
    Demo().configure_traits()
