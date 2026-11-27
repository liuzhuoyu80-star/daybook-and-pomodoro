import sys
from functools import partial
from math import cos, exp, pi, sin
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPoint, QPointF, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QCursor, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QGraphicsDropShadowEffect, QGraphicsEffect, QFrame, QHBoxLayout, QLCDNumber, QMenu,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)
from PySide6.QtSvg import QSvgRenderer
from countdown import Countdown
from click_flash import ClickFlash

COLORS = {"Work": "#424850", "Rest": "#405651"}
CONTROL_KEY = "#383d42"
LETTERING = {COLORS["Work"]: "#eadbb8", COLORS["Rest"]: "#c0e1d0", CONTROL_KEY: "#e0e1db"}
LCD = {"Work": "#b6bd9f", "Rest": "#10201a"}
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



BURST_MS = 480
GAP_MS = 220
ALERT_MS = 3 * BURST_MS + 2 * GAP_MS


class VibrationEffect(QGraphicsEffect):
    """Crossfade a cached Gaussian exposure and displace narrow scan lines."""
    def __init__(self, snapshot):
        super().__init__()
        self.sharp = snapshot
        self.soft = QPixmap(snapshot.size())
        self.soft.setDevicePixelRatio(snapshot.devicePixelRatio())
        self.soft.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.soft)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        # Horizontal shutter exposure. Normalize to exactly 255 alpha levels
        # so that repeated additive blends preserve the face brightness.
        kernel = [exp(-.5 * (x / 17)**2) for x in range(-48, 49)]
        total = sum(kernel)
        cumulative = previous = 0
        for x, weight in enumerate(kernel, -48):
            cumulative += weight
            level = round(255 * cumulative / total)
            if level > previous:
                painter.setOpacity((level - previous) / 255)
                painter.drawPixmap(QPointF(x, 0), snapshot)
            previous = level
        painter.end()
        self.phase = self.strength = 0

    def draw(self, painter):
        painter.save()
        if self.strength < 1:
            painter.setOpacity(1 - self.strength)
            painter.drawPixmap(0, 0, self.sharp)
        painter.setOpacity(self.strength)
        painter.drawPixmap(0, 0, self.soft)
        width = self.sharp.deviceIndependentSize().width()
        for n, y in enumerate((5, 16, 27, 39, 48, 57, 68, 77)):
            direction = cos(self.phase + n * .8)
            x = (width - 66) * (.5 + .48 * sin(self.phase * .26 + n * 2))
            painter.save()
            painter.setClipRect(QRectF(x, y, 65, 2 + n % 3))
            painter.drawPixmap(QPointF(16 * direction, 0), self.soft)
            painter.restore()
            painter.setPen(QPen(QColor(210, 219, 191, 44), .7))
            painter.drawLine(QPointF(x, y), QPointF(x + 18 + 31 * abs(direction), y))
        painter.restore()



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
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(0)
        self.fields = []
        for index in range(3):
            if index:
                colon = self.lcd(1)
                colon.setFixedWidth(7)
                colon.display(":")
                row.addWidget(colon)
            field = self.lcd(2)
            field.setAccessibleName(("小时", "分钟", "秒")[index])
            row.addWidget(field, 1)
            self.fields.append(field)
        self.selected = None
        self.residual = 0
        self.press_point = None
        self.dragging = False

    def lcd(self, digits):
        field = QLCDNumber(digits, self)
        field.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        field.setFrameShape(QFrame.Shape.NoFrame)
        field.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        field.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        return field

    def select(self, index):
        self.selected = index
        self.residual = 0
        for i, field in enumerate(self.fields):
            field.setStyleSheet("background:rgba(125,125,125,65); border-radius:4px;" if i == index else "")

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
            field.display(f"{value:02d}")
        if self.property("mode") != mode:
            self.setProperty("mode", mode)
            night = mode == "Rest"
            ink = "#bdeda9" if night else "#222e26"
            self.setStyleSheet(f"QFrame#display {{ background:{LCD[mode]}; }}"
                               f"QLCDNumber {{ color:{ink}; }}")
            for digit in self.findChildren(QLCDNumber):
                glow = None
                if night:
                    glow = QGraphicsDropShadowEffect(digit)
                    glow.setOffset(0, 0)
                    glow.setBlurRadius(5)
                    glow.setColor(QColor(130, 224, 146, 165))
                digit.setGraphicsEffect(glow)


class TimerWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("浮动番茄钟 v0.2 · LCD")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.model = Countdown()
        self.click_flash = ClickFlash(self)
        self.face = TimeDisplay()
        self.face.adjusted.connect(self.adjust)
        self.face.pressed.connect(self.finish_alert)
        self.alert_anchor = None
        self.alert = QVariantAnimation(self)
        self.alert.setStartValue(0.0)
        self.alert.setEndValue(1.0)
        self.alert.setDuration(ALERT_MS)
        self.alert.valueChanged.connect(self.paint_alert)
        self.alert.finished.connect(self.finish_alert)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("panel")
        self.panel = panel
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
            QFrame#display { border:3px solid #363a3c; border-top-color:#262a2b; border-bottom-color:#64696a; border-radius:4px; }
            QLCDNumber { color:#222e26; background:transparent; border:none; }
            QPushButton { font:600 11px 'Consolas'; padding:0; border-radius:3px; }
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
        self.click_flash.watch(button)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lettering = LETTERING[color or CONTROL_KEY]
        if text in ICONS:
            label, shape = ICONS[text]
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setText("")
            button.setIcon(control_icon(shape, lettering))
            button.setIconSize(QSize(16, 16))
        enamel = QColor(color or CONTROL_KEY)
        button.setStyleSheet(f"""
            QPushButton {{ background:{enamel.name()}; color:{lettering};
                border:1px solid {enamel.darker(155).name()};
                border-top-color:{enamel.lighter(120).name()};
                border-bottom:2px solid {enamel.darker(160).name()}; }}
            QPushButton:hover {{ background:{enamel.lighter(110).name()}; }}
            QPushButton:checked {{ border:2px solid {lettering}; }}
            QPushButton:pressed {{ background:{enamel.darker(110).name()}; }}
        """)
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
                self.vibration = VibrationEffect(self.panel.grab())
                self.panel.setGraphicsEffect(self.vibration)
                self.paint_alert(0)
                self.alert.start()
                return
            self.model.start()
        self.show_model()

    def paint_alert(self, progress):
        if self.alert_anchor is None:
            return
        elapsed = progress * ALERT_MS
        within_burst = elapsed % (BURST_MS + GAP_MS)
        pulse = min(1.0, within_burst / BURST_MS)
        envelope = min(1.0, pulse / .15, (1 - pulse) / .22)
        phase = 2 * pi * 6 * pulse
        self.move(self.alert_anchor + QPoint(round(5 * envelope * sin(phase)), 0))
        self.vibration.phase = phase
        self.vibration.strength = envelope * (.98 + .02 * abs(cos(phase)))
        self.vibration.update()

    def finish_alert(self):
        if self.alert_anchor is None:
            return
        self.alert.stop()
        self.move(self.alert_anchor)
        self.alert_anchor = None
        self.panel.setGraphicsEffect(None)
        self.vibration = None
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
