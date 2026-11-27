import sys
from functools import partial
from math import pi, sin
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPoint, QVariantAnimation
from PySide6.QtGui import QColor, QCursor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMenu,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)
from PySide6.QtSvg import QSvgRenderer
from countdown import Countdown

COLORS = {"Work": "#abd5b5", "Rest": "#ecc0a2"}
ICONS = {
    "Work": ("工作", '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V4h8v3M3 12q9 5 18 0"/>'),
    "Rest": ("休息", '<path d="M3 8h13v6a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5zM16 9h2a3 3 0 0 1 0 6h-2M3 22h15M7 3v2m5-2v2"/>'),
    "start": ("开始或继续", '<path fill="currentColor" d="M7 4l12 8-12 8z"/>'),
    "reset": ("重置", '<path d="M4 5v6h6M5 10a8 8 0 1 1 1 9"/>'),
    "pause": ("暂停", '<path stroke-width="4" d="M8 5v14M16 5v14"/>'),
}


def control_icon(shape, color):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'color="{color}" stroke="{color}" fill="none" stroke-width="2" '
           f'stroke-linecap="round" stroke-linejoin="round">{shape}</svg>')
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    return QIcon(pixmap)



class TimeDisplay(QFrame):
    adjusted = Signal(int)
    pressed = Signal()
    units = (3600, 60, 1)

    def __init__(self):
        super().__init__()
        self.setObjectName("display")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setToolTip("点击时、分或秒后滚动调整。拖动数字可移动窗口。")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(0)
        self.fields = []
        for i in range(3):
            if i:
                row.addWidget(QLabel(":"))
            field = QLabel("00")
            field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(field, 1)
            self.fields.append(field)
        self.selected = None
        self.residual = 0
        self.press_point = None
        self.dragging = False

    def select(self, index):
        self.selected = index
        self.residual = 0
        for i, field in enumerate(self.fields):
            field.setStyleSheet("background:rgba(255,255,255,115); border-radius:4px;" if i == index else "")

    def focusOutEvent(self, event):
        self.select(None)
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit()
            self.setFocus()
            self.press_point = event.globalPosition().toPoint()
            self.offset = self.press_point - self.window().pos()
            self.dragging = False
            x = event.position().x()
            self.select(min(range(3), key=lambda i: abs(self.fields[i].geometry().center().x() - x)))

    def mouseMoveEvent(self, event):
        if self.press_point is not None:
            pos = event.globalPosition().toPoint()
            if (pos - self.press_point).manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
            if self.dragging:
                self.window().move(pos - self.offset)

    def mouseReleaseEvent(self, event):
        self.press_point = None

    def wheelEvent(self, event):
        if self.selected is None or not self.hasFocus():
            event.ignore()
            return
        self.residual += event.angleDelta().y()
        steps = int(self.residual / 120)
        if steps:
            self.residual -= steps * 120
            self.adjusted.emit(steps * self.units[self.selected])
        event.accept()

    def display(self, seconds, mode):
        hours, rest = divmod(seconds, 3600)
        minutes, seconds = divmod(rest, 60)
        for field, value in zip(self.fields, (hours, minutes, seconds)):
            field.setText(f"{value:02d}")
        if self.property("mode") != mode:
            self.setProperty("mode", mode)
            self.setStyleSheet(f"QFrame#display {{ background:{COLORS[mode]}; }}")


class TimerWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("浮动番茄钟")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.model = Countdown()
        self.face = TimeDisplay()
        self.face.adjusted.connect(self.adjust)
        self.face.pressed.connect(self.finish_alert)
        self.alert_anchor = None
        self.alert = QVariantAnimation(self)
        self.alert.setStartValue(0.0)
        self.alert.setEndValue(1.0)
        self.alert.setDuration(2400)
        self.alert.valueChanged.connect(self.paint_alert)
        self.alert.finished.connect(self.finish_alert)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("panel")
        shell.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        top = QHBoxLayout()
        layout.addLayout(top, 1)
        top.setSpacing(2)
        modes = QVBoxLayout()
        top.addLayout(modes)
        modes.setSpacing(2)
        self.mode_buttons = {}
        for mode, color in COLORS.items():
            button = self.button(mode, partial(self.model.force_mode, mode), color)
            button.setCheckable(True)
            button.setFixedWidth(31)
            modes.addWidget(button, 1)
            self.mode_buttons[mode] = button
        controls = QVBoxLayout()
        top.addLayout(controls, 1)
        controls.setSpacing(2)
        controls.addWidget(self.face, 1)
        buttons = QHBoxLayout()
        controls.addLayout(buttons)
        buttons.setSpacing(2)
        for name, action in (("start", self.model.start), ("reset", self.model.reset),
                             ("pause", self.model.pause)):
            button = self.button(name, action)
            button.setFixedHeight(20)
            buttons.addWidget(button, 1)
        presets = QHBoxLayout()
        layout.addLayout(presets)
        presets.setSpacing(2)
        for minutes, mode in ((5, "Rest"), (10, "Rest"), (25, "Work"), (40, "Work")):
            seconds = minutes * 60
            button = self.button(f"{minutes}min", partial(self.model.set_duration, seconds, mode=mode),
                                 COLORS[mode])
            button.setFixedHeight(20)
            presets.addWidget(button, 1)
        self.setStyleSheet("""
            QFrame#panel { background:transparent; border:0; }
            QFrame#display, QPushButton { background:#365354; border:0; border-radius:4px; }
            QLabel { color:#172c27; font:600 22px 'Consolas'; }
            QPushButton { color:#fff; font:600 11px 'Segoe UI'; padding:0; }
            QPushButton:hover { border:1px solid #839c99; }
            QPushButton:pressed { background:#283f40; }
        """)
        self.setFixedSize(206, 86)
        rect = QApplication.screenAt(QCursor.pos()).availableGeometry() if QApplication.screenAt(QCursor.pos()) else QApplication.primaryScreen().availableGeometry()
        self.move(rect.right() - self.width() - 15, rect.bottom() - self.height() - 15)
        self.shortcut = QShortcut(QKeySequence("Alt+F4"), self)
        self.shortcut.activated.connect(self.close)
        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def button(self, text, action, color=None):
        button = QPushButton(text)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if text in ICONS:
            label, shape = ICONS[text]
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setText("")
            button.setIcon(control_icon(shape, "#233c32" if color else "#f3f6ef"))
            button.setIconSize(QSize(16, 16))
        if color:
            button.setStyleSheet(f"QPushButton {{ background:{color}; color:#193139; }}"
                                 "QPushButton:checked { border:2px solid #193139; font-weight:bold; }")
        button.clicked.connect(lambda checked=False: self.perform(action))
        return button

    def perform(self, action):
        self.refresh()
        self.finish_alert()
        action()
        self.refresh()

    def adjust(self, delta):
        self.perform(partial(self.model.adjust, delta))

    def refresh(self):
        if self.alert_anchor is not None:
            return
        if self.model.tick():
            QApplication.beep()
            if self.model.mode == "Rest":
                self.face.display(0, "Work")
                self.alert_anchor = self.pos()
                self.paint_alert(0)
                self.alert.start()
                return
            self.model.start()
        self.show_model()

    def paint_alert(self, progress):
        if self.alert_anchor is None:
            return
        pulse = sin(3 * pi * progress) ** 2
        base = QColor(COLORS["Work"])
        red = QColor("#f49b91")
        rgb = [round(a + (b - a) * pulse)
               for a, b in zip(base.getRgb()[:3], red.getRgb()[:3])]
        fill = QColor(*rgb).name()
        edge = QColor.fromRgb(255, 92, 77, round(230 * pulse)).name(QColor.NameFormat.HexArgb)
        self.face.setStyleSheet(f"QFrame#display {{ background:{fill}; border:2px solid {edge}; }}")
        self.move(self.alert_anchor - QPoint(0, round(4 * pulse)))

    def finish_alert(self):
        if self.alert_anchor is None:
            return
        self.alert.stop()
        self.move(self.alert_anchor)
        self.alert_anchor = None
        self.face.setProperty("mode", None)
        self.model.start()
        self.show_model()

    def show_model(self):
        self.face.display(self.model.remaining, self.model.mode)
        for mode, button in self.mode_buttons.items():
            button.setChecked(mode == self.model.mode)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("退出番茄钟", self.close)
        menu.exec(event.globalPos())
        menu.deleteLater()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TimerWindow()
    window.show()
    sys.exit(app.exec())
