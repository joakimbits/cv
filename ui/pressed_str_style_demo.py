# file: qss_state_preview.py
from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets


class PressPropFilter(QtCore.QObject):
    """Emulate :pressed via [pressed='true'] set on the *editor* (not its viewport)."""
    def _target(self, obj: QtCore.QObject) -> QtWidgets.QWidget | None:
        # QLineEdit events arrive on the widget itself
        if isinstance(obj, QtWidgets.QLineEdit):
            return obj
        # QTextEdit: mouse events usually arrive on viewport(); map to parent QTextEdit
        if isinstance(obj, QtWidgets.QWidget) and isinstance(obj.parent(), QtWidgets.QTextEdit):
            return obj.parent()  # the QTextEdit
        # Fallback: direct events on QTextEdit
        if isinstance(obj, QtWidgets.QTextEdit):
            return obj
        return None

    def _set_pressed(self, w: QtWidgets.QWidget, val: bool) -> None:
        if w.property("pressed") == val:
            return
        w.setProperty("pressed", val)
        w.style().unpolish(w); w.style().polish(w)
        w.update()

    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if isinstance(ev, QtGui.QMouseEvent):
            tgt = self._target(obj)
            if tgt and ev.type() == QtCore.QEvent.MouseButtonPress and ev.button() == QtCore.Qt.LeftButton:
                self._set_pressed(tgt, True)
            elif tgt and ev.type() == QtCore.QEvent.MouseButtonRelease and ev.button() == QtCore.Qt.LeftButton:
                self._set_pressed(tgt, False)
        return super().eventFilter(obj, ev)


def make_editor_pair(title: str, long_text: bool = False) -> QtWidgets.QGroupBox:
    g = QtWidgets.QGroupBox(title)
    v = QtWidgets.QVBoxLayout(g)
    v.setContentsMargins(12, 10, 12, 10)
    v.setSpacing(8)

    # One-line editor
    le = QtWidgets.QLineEdit()
    le.setPlaceholderText("QLineEdit — hover, focus, pressed")
    le.setFrame(False)  # QSS will draw borders

    # Wrapped editor
    te = QtWidgets.QTextEdit()
    te.setPlaceholderText("QTextEdit — hover, focus, pressed")
    te.setFrameStyle(QtWidgets.QFrame.NoFrame)  # QSS will draw borders
    if long_text:
        te.setPlainText(
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n"
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n"
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip."
        )

    # Simulated pressed state on both (IMPORTANT: install on QTextEdit *and* its viewport)
    f = PressPropFilter(g)
    le.installEventFilter(f)
    te.installEventFilter(f)
    te.viewport().installEventFilter(f)

    v.addWidget(le)
    v.addWidget(te)
    return g


def main():
    app = QtWidgets.QApplication([])

    # QSS: unified visuals for QLineEdit and QTextEdit
    app.setStyleSheet("""
    /* Base: remove native frames; add padding so borders are visible */
    QLineEdit, QTextEdit {
        border: none;
        border-radius: 6px;
        background: palette(Base);
        padding: 6px 8px;   /* <-- critical for QTextEdit: keeps viewport away from the border */
    }

    /* Hover: background only, to avoid fighting with focus underline */
    QLineEdit:hover:enabled, QTextEdit:hover:enabled {
        background: palette(AlternateBase);
    }

    /* Focus: blue underline */
    QLineEdit:focus, QTextEdit:focus {
        border-bottom: 2px solid palette(Highlight);
    }

    /* Pressed: full outline (overrides focus underline by being later) */
    QLineEdit[pressed="true"], QTextEdit[pressed="true"] {
        border: 2px solid palette(Highlight);
        border-radius: 6px;
        background: palette(Base);
    }
    """)

    w = QtWidgets.QWidget()
    w.setWindowTitle("Qt pseudo-states preview: :hover, :focus, [pressed]")
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(12)

    lay.addWidget(make_editor_pair("Short editors"))
    lay.addWidget(make_editor_pair("Wrapped editor with content", long_text=True))
    lay.addStretch(1)

    w.resize(640, 420)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
