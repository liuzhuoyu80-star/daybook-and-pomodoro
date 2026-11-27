from math import cos, pi, sin

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPen, qGray, qRgb
from PySide6.QtWidgets import QApplication, QWidget


class ClickFlash(QWidget):
    radius = 20

    def __init__(self, parent):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput |
                 Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(2 * self.radius + 1, 2 * self.radius + 1)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setTimerType(Qt.TimerType.PreciseTimer)
        self.timeout.timeout.connect(self.hide)

    def watch(self, button):
        button.installEventFilter(self)
        # Refresh the sampled face when a press or a mode change repaints the key.
        button.pressed.connect(self.update)
        button.released.connect(self.update)

    def eventFilter(self, button, event):
        if (event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
                and event.button() == Qt.MouseButton.LeftButton):
            self.flash(event.globalPosition().toPoint())
        return False

    def flash(self, center):
        self.hide()
        screen = QApplication.screenAt(center) or self.parentWidget().screen()
        self.setScreen(screen)
        corner = center - QPoint(self.radius, self.radius)
        self.move(corner)
        ratio = screen.devicePixelRatio()
        side = round(self.width() * ratio)
        self.backdrop = QImage(side, side, QImage.Format.Format_RGB32)
        self.backdrop.setDevicePixelRatio(ratio)
        self.backdrop.fill(Qt.GlobalColor.black)
        area = QRect(corner, self.size())
        painter = QPainter(self.backdrop)
        for display in QApplication.screens():
            part = area.intersected(display.geometry())
            if not part.isEmpty():
                offset = part.topLeft() - display.geometry().topLeft()
                sample = display.grabWindow(0, offset.x(), offset.y(), part.width(), part.height())
                painter.drawPixmap(part.topLeft() - corner, sample)
        painter.end()
        self.show()
        self.update()
        self.timeout.start(120)

    def paintEvent(self, event):
        # Composite the live LCD face over the desktop, including its transparent gaps.
        background = self.backdrop.copy()
        window = self.parentWidget()
        painter = QPainter(background)
        painter.drawPixmap(window.mapToGlobal(QPoint()) - self.pos(), window.grab())
        painter.end()

        # Rasterize without antialiasing so each visible pixel is pure black or white.
        ink = QImage(background.size(), QImage.Format.Format_ARGB32_Premultiplied)
        ink.setDevicePixelRatio(background.devicePixelRatio())
        ink.fill(Qt.GlobalColor.transparent)
        painter = QPainter(ink)
        painter.translate(self.radius + 0.5, self.radius + 0.5)
        painter.setPen(QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        for i in range(8):
            angle = i * pi / 4
            direction = QPointF(cos(angle), sin(angle))
            painter.drawLine(direction * 5, direction * 18)
        painter.end()
        for y in range(ink.height()):
            for x in range(ink.width()):
                if ink.pixel(x, y) and qGray(background.pixel(x, y)) >= 128:
                    ink.setPixel(x, y, qRgb(0, 0, 0))
        painter = QPainter(self)
        painter.drawImage(QPoint(), ink)
        painter.end()
