import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QConicalGradient, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QPolygonF, QTransform
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from countdown import Countdown


# The inset, moving LCD segments and side controls share one design space.
FRAME = QRectF(19, 9, 293, 219)
KEYS = {
    "Work": (QRectF(19, 68, 32, 43), "工作模式"),
    "Rest": (QRectF(19, 129, 32, 45), "休息模式"),
    "run": (QRectF(280, 68, 32, 43), "开始 / 暂停"),
    "reset": (QRectF(280, 129, 32, 45), "重置本轮"),
}
FIELDS = (
    (QRectF(92, 115, 50, 46), 3600, "小时"),
    (QRectF(150, 115, 50, 46), 60, "分钟"),
    (QRectF(201, 115, 39, 46), 1, "秒"),
)
DIGITS = ("abcdef", "bc", "abdeg", "abcdg", "bcfg", "acdfg", "acdefg", "abc", "abcdefg", "abcdfg")
# Broad shoulders and tapered ends of the original twisted-nematic LCD.
STROKES = {
    "a": [(2, 1), (4, 0), (14, 0), (16, 2), (13, 4), (5, 4)],
    "b": [(16, 2.5), (17, 4), (17, 14), (15, 16.5), (13, 14.5), (13, 5)],
    "c": [(15, 17.5), (17, 19), (17, 30), (15.5, 33), (13, 30), (13, 20)],
    "d": [(2, 31.5), (5, 30), (13, 30), (15, 33.5), (3.5, 34), (1, 33)],
    "e": [(2, 18), (4.5, 20), (4.5, 29), (1.5, 32), (0.5, 30), (0.5, 20)],
    "f": [(2, 2), (4.5, 5), (4.5, 14), (2.5, 16), (0.5, 14), (0.5, 5)],
    "g": [(2.5, 17), (5, 15), (12.5, 15), (15, 17), (12.5, 19), (5, 19)],
}


def polygon(points):
    return QPolygonF([QPointF(x, y) for x, y in points])


SEGMENT_SHAPES = {name: polygon(points) for name, points in STROKES.items()}


def bezel_outline():
    # A continuous side rail, long sloping shoulders and a short flat at each end.
    path = QPainterPath(QPointF(80, 13))
    path.lineTo(251, 13)
    path.cubicTo(256, 13, 258, 14, 261, 19)
    path.lineTo(281, 55)
    path.cubicTo(287, 66, 290, 74, 290, 87)
    path.lineTo(290, 150)
    path.cubicTo(290, 163, 287, 171, 281, 182)
    path.lineTo(261, 218)
    path.cubicTo(258, 223, 256, 224, 251, 224)
    path.lineTo(80, 224)
    path.cubicTo(75, 224, 73, 223, 70, 218)
    path.lineTo(50, 182)
    path.cubicTo(44, 171, 41, 163, 41, 150)
    path.lineTo(41, 87)
    path.cubicTo(41, 74, 44, 66, 50, 55)
    path.lineTo(70, 19)
    path.cubicTo(73, 14, 75, 13, 80, 13)
    path.closeSubpath()
    return path


def insert_outline():
    path = QPainterPath(QPointF(85, 24))
    path.lineTo(245, 24)
    path.quadTo(253, 24, 258, 34)
    path.lineTo(270, 57)
    path.quadTo(278, 70, 278, 82)
    path.lineTo(278, 157)
    path.quadTo(278, 168, 272, 179)
    path.lineTo(259, 203)
    path.quadTo(254, 213.5, 245, 213.5)
    path.lineTo(86, 213.5)
    path.quadTo(77, 213.5, 72, 203)
    path.lineTo(59, 179)
    path.quadTo(53, 168, 53, 157)
    path.lineTo(53, 82)
    path.quadTo(53, 70, 61, 57)
    path.lineTo(73, 34)
    path.quadTo(78, 24, 85, 24)
    path.closeSubpath()
    return path


def printed_border():
    # Trace the outside edge of the printed black border in watch.png coordinates.
    inner = QPainterPath(QPointF(45, 15.5))
    inner.lineTo(183, 15.5)
    inner.cubicTo(194, 15.5, 198.5, 20.5, 202, 27)
    inner.lineTo(210, 42)
    inner.cubicTo(214, 49.5, 214.5, 55, 214.5, 64)
    inner.lineTo(215.3, 130)
    inner.cubicTo(215.3, 143, 214, 150, 210, 158)
    inner.lineTo(202, 173)
    inner.cubicTo(198.5, 179.5, 192.5, 182, 183, 182)
    inner.lineTo(44, 182.5)
    inner.cubicTo(35, 182.5, 31.5, 177, 28, 171)
    inner.lineTo(21, 158)
    inner.cubicTo(16.5, 149, 15, 143.5, 15, 132)
    inner.cubicTo(14.5, 110, 14.5, 83, 15, 61)
    inner.cubicTo(15, 52, 16.5, 46, 20, 39.5)
    inner.lineTo(27.5, 25)
    inner.cubicTo(31, 18.5, 36.5, 15.5, 45, 15.5)
    inner.closeSubpath()
    return inner.translated(51, 21)


def metal_gradient(stops):
    finish = QConicalGradient(QPointF(165.5, 118.5), 0)
    for stop, color in stops:
        finish.setColorAt(stop, QColor(color))
    return finish


def make_bezel():
    outline = bezel_outline()
    # The darker sidewall and a narrow satin bevel follow the same silhouette.
    bezel = QPixmap(312 * 3, 228 * 3)
    bezel.setDevicePixelRatio(3)
    bezel.fill(Qt.GlobalColor.transparent)
    p = QPainter(bezel)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillPath(outline, QColor("#30363c"))
    finish = metal_gradient([(0, "#889399"), (.13, "#c3ccca"), (.25, "#748087"),
                             (.36, "#aab4b5"), (.48, "#a0abad"), (.62, "#535e66"),
                             (.75, "#515a63"), (.87, "#818d94"), (1, "#889399")])
    for horizontal, vertical, brush in [(1.6, 1.7, finish), (6.4, 6.2, QColor("#30353c"))]:
        tr = QTransform()
        tr.translate(165.5, 118.5)
        tr.scale(1 - horizontal / 124.5, 1 - vertical / 105.5)
        tr.translate(-165.5, -118.5)
        p.fillPath(tr.map(outline), brush)
    # A thin light lip marks the transition from steel to the gold insert.
    p.setPen(QPen(QColor("#a59c87"), 2.3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(insert_outline())
    p.end()
    return bezel


def draw_switch(p, key, pressed):
    zone = KEYS[key][0]
    p.fillRect(zone, QColor(0, 0, 0, 1))
    y = zone.center().y()
    p.save()
    if key in ("run", "reset"):
        p.translate(331, 0)
        p.scale(-1, 1)
    # A short, broad cap travels into the stationary, tapered mounting boss.
    x = 24.5 if pressed else 20.5
    cap = QRectF(x, y - 8, 18, 16)
    finish = QLinearGradient(0, cap.top(), 0, cap.bottom())
    for stop, color in [(0, "#bdc4c3"), (.33, "#9da8ab"), (1, "#69757b")]:
        finish.setColorAt(stop, QColor(color))
    p.setPen(QPen(QColor("#4c5458"), 1.1))
    p.setBrush(finish)
    p.drawRoundedRect(cap, 3.6, 3.6)
    if key in ("Rest", "reset"):
        p.translate(0, 2 * y)
        p.scale(1, -1)
    boss = QPainterPath(QPointF(51, y - 29))
    boss.cubicTo(43, y - 25, 35, y - 23, 32.5, y - 16)
    boss.quadTo(31, y - 12, 31, y - 8)
    boss.lineTo(31, y + 13)
    boss.quadTo(31, y + 17, 34.5, y + 18.5)
    boss.lineTo(51, y + 23)
    boss.closeSubpath()
    satin = QLinearGradient(31, 0, 46, 0)
    for stop, color in [(0, "#c1c8c7"), (.28, "#a7b0b1"), (1, "#78858b")]:
        satin.setColorAt(stop, QColor(color))
    p.setBrush(satin)
    p.setPen(QPen(QColor("#4b555b"), 1.1))
    p.drawPath(boss)
    p.restore()


def draw_digit(painter, x, y, size, digit):
    painter.save()
    painter.translate(x, y)
    painter.scale(size, size)
    painter.shear(-0.055, 0)
    for segment in DIGITS[int(digit)]:
        painter.drawPolygon(SEGMENT_SHAPES[segment])
    painter.restore()


class Watch(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("浮动番茄钟 v0.4")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)
        self.setFixedSize(164, 123)
        self.insert = QPixmap(str(Path(__file__).with_name("watch.png")))
        if self.insert.isNull():
            raise RuntimeError("缺少表盘纹理 watch.png")
        self.insert_clip = insert_outline()
        border = printed_border()
        self.band = QPainterPath(self.insert_clip)
        self.band.setFillRule(Qt.FillRule.OddEvenFill)
        self.band.addPath(border)
        # The fine printed rule follows the heavy border about four source pixels out.
        offset = QPainterPathStroker()
        offset.setWidth(8.6)
        offset.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.fine_rule = border.united(offset.createStroke(border))
        self.bezel = make_bezel()
        self.model = Countdown()
        self.selected = self.pressed = self.press_point = None
        self.dragging = False
        self.residual = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        self.move(bounds.right() - self.width() - 14, bounds.bottom() - self.height() - 14)

    def refresh(self):
        if self.model.tick():
            QApplication.beep()
            self.model.start()
        self.update()

    def apply(self, key):
        self.refresh()
        if key == "run":
            if self.model.deadline is None:
                self.model.start()
            else:
                self.model.pause()
        elif key == "reset":
            self.model.reset()
        else:
            self.model.force_mode(key)
        self.update()

    def hit(self, pos):
        pt = QPointF(FRAME.left() + pos.x() * FRAME.width() / self.width(),
                     FRAME.top() + pos.y() * FRAME.height() / self.height())
        for key, (zone, _) in KEYS.items():
            if zone.contains(pt):
                return key
        for i, (zone, _, _) in enumerate(FIELDS):
            if zone.contains(pt):
                return i
        return None

    def select(self, field):
        self.selected = field
        self.residual = 0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.pressed = self.hit(event.position())
            self.select(self.pressed if isinstance(self.pressed, int) else None)
            self.press_point = event.globalPosition().toPoint()
            self.offset = self.press_point - self.pos()
            self.dragging = False

    def mouseMoveEvent(self, event):
        if self.press_point is not None and self.pressed not in KEYS:
            point = event.globalPosition().toPoint()
            if (point - self.press_point).manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
            if self.dragging:
                self.select(None)
                self.move(point - self.offset)
        target = self.hit(event.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if target is not None else Qt.CursorShape.ArrowCursor)
        if target in KEYS:
            self.setToolTip(KEYS[target][1])
        elif isinstance(target, int):
            self.setToolTip(f"点击后滚轮调整{FIELDS[target][2]}")
        else:
            self.setToolTip("拖动表壳移动 · 右键退出")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.pressed in KEYS and self.pressed == self.hit(event.position()):
                self.apply(self.pressed)
            self.pressed = self.press_point = None
            self.dragging = False
            self.update()

    def focusOutEvent(self, event):
        self.select(None)
        super().focusOutEvent(event)

    def wheelEvent(self, event):
        if self.selected is None or not self.hasFocus():
            event.ignore()
            return
        self.residual += event.angleDelta().y()
        steps = int(self.residual / 120)
        if steps:
            self.refresh()
            self.residual -= steps * 120
            self.model.adjust(steps * FIELDS[self.selected][1])
            self.update()
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("退出番茄钟", self.close)
        menu.exec(event.globalPos())
        menu.deleteLater()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(self.width() / FRAME.width(), self.height() / FRAME.height())
        p.translate(-FRAME.left(), -FRAME.top())
        for key in KEYS:
            draw_switch(p, key, self.pressed == key)
        p.drawPixmap(0, 0, self.bezel)
        p.save()
        p.setClipPath(self.insert_clip)
        p.drawPixmap(51, 21, self.insert)
        p.restore()
        # Punch through the photo and the opaque metal backing to reveal the desktop.
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        p.fillPath(self.band, Qt.GlobalColor.black)
        p.restore()
        p.setPen(QPen(QColor("#2d231e"), 1.45))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(self.fine_rule)

        ink = QColor(37, 32, 17, 224)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        hours, remainder = divmod(self.model.remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        for x, y, size, value in [(100, 121, 1, hours), (159, 121, 1, minutes), (205, 129, 0.76, seconds)]:
            for i, digit in enumerate(f"{value:02}"):
                draw_digit(p, x + i * 22 * size, y, size, digit)
        for y in (131, 146):
            p.drawEllipse(QPointF(146, y), 1.9, 2.1)
        font = QFont("Consolas")
        font.setPixelSize(15)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(font)
        p.setPen(ink)
        p.drawText(QRectF(100, 92, 132, 22), Qt.AlignmentFlag.AlignCenter, self.model.mode.upper())
        p.setPen(Qt.PenStyle.NoPen)
        if self.model.deadline is not None:
            p.drawPolygon(polygon([(222, 97), (222, 108), (230, 102.5)]))
        elif self.model.remaining != self.model.durations[self.model.mode]:
            for x in (222, 227):
                p.fillRect(QRectF(x, 98, 2.6, 10), ink)
        if self.selected is not None:
            zone = FIELDS[self.selected][0]
            p.setPen(QPen(QColor(60, 45, 22, 170), 1.4))
            p.drawLine(QPointF(zone.left() + 5, 158), QPointF(zone.right() - 4, 158))
        p.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    watch = Watch()
    watch.show()
    sys.exit(app.exec())
