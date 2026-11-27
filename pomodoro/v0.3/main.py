import math
import sys
from time import monotonic

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient, QCursor)
from PySide6.QtWidgets import QApplication, QMenu, QToolTip, QWidget


LIMIT = 3600
CENTER = QPointF(100, 114)
GREEN = QRectF(25, 4, 86, 18)
ORANGE = QRectF(143, 5, 31, 17)


def gradient(x1, y1, x2, y2, stops):
    result = QLinearGradient(x1, y1, x2, y2)
    for position, color in stops:
        result.setColorAt(position, QColor(color))
    return QBrush(result)


def circle_point(angle, radius):
    return CENTER + QPointF(math.sin(angle) * radius, -math.cos(angle) * radius)


class WheelDial:
    """Detents select a precise target. Motion eases toward it separately."""
    def __init__(self):
        self.clear()

    def clear(self):
        self.last = None
        self.direction = 0
        self.fraction = 0

    def change(self, ticks, now):
        direction = 1 if ticks > 0 else -1
        if direction != self.direction or self.last is None or now - self.last > .45:
            self.fraction = 0
            speed = 0
        else:
            speed = abs(ticks) / max(.012, now - self.last)
        self.last, self.direction = now, direction
        step = 120 if speed >= 14 else 60 if speed >= 8 else 15 if speed >= 4 else 5
        self.fraction += ticks * step
        delta = math.trunc(self.fraction)
        self.fraction -= delta
        return delta


class DialTimer(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("浮动番茄钟 v0.3")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setFixedSize(200, 208)
        self.preset = self.remaining = 25 * 60
        self.shown = float(self.remaining)
        self.deadline = None
        self.armed = False
        self.wheel = WheelDial()
        self.drag = self.pressed = None
        self.last_frame = monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.frame)
        self.timer.start(100)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        bounds = screen.availableGeometry()
        self.move(bounds.right()-self.width()-15, bounds.bottom()-self.height()-15)

    def frame(self):
        now = monotonic()
        if self.deadline is not None:
            self.remaining = max(0, math.ceil(self.deadline - now))
            if not self.remaining:
                self.deadline = None
                QApplication.beep()
        dt = now - self.last_frame
        self.last_frame = now
        self.shown += (self.remaining-self.shown) * (1-math.exp(-dt/.075))
        moving = abs(self.remaining-self.shown) > .08
        if not moving:
            self.shown = self.remaining
        interval = 16 if moving else 100
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.update()

    def hit(self, p):
        if GREEN.contains(p):
            return "toggle"
        if ORANGE.contains(p):
            return "reset"
        if (p-CENTER).manhattanLength() <= 30 and math.hypot(p.x()-100, p.y()-114) <= 22:
            return "knob"
        return "case"

    def mousePressEvent(self, event):
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            return
        self.pressed = self.hit(event.position())
        self.armed = self.pressed == "knob"
        self.wheel.clear()
        if self.pressed == "case":
            self.drag = event.globalPosition().toPoint() - self.pos()
        self.update()

    def mouseMoveEvent(self, event):
        if self.drag is not None:
            self.move(event.globalPosition().toPoint()-self.drag)
        target = self.hit(event.position())
        self.setCursor(Qt.CursorShape.ArrowCursor if target == "case" else Qt.CursorShape.PointingHandCursor)
        self.setToolTip({"toggle":"开始 / 暂停","reset":"重置到上次设定时长",
                         "knob":"点选旋钮，快滚粗调，慢滚微调","case":"拖动外壳移动，右键退出"}[target])

    def mouseReleaseEvent(self, event):
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            return
        target = self.hit(event.position())
        if target == self.pressed == "toggle":
            if self.deadline is None:
                if not self.remaining:
                    self.remaining = self.preset
                self.deadline = monotonic()+self.remaining
            else:
                self.frame()
                self.deadline = None
        elif target == self.pressed == "reset":
            self.deadline = None
            self.remaining = self.preset
        self.drag = self.pressed = None
        self.frame()

    def wheelEvent(self, event):
        if not self.armed:
            event.ignore()
            return
        ticks = event.angleDelta().y()/120 or event.pixelDelta().y()/40
        if ticks:
            self.frame()
            now = monotonic()
            self.remaining = self.preset = max(1,min(LIMIT,self.remaining+self.wheel.change(ticks,now)))
            if self.deadline is not None:
                self.deadline = now+self.remaining
            self.timer.setInterval(16)
            self.update()
        event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("退出番茄钟",self.close)
        menu.exec(event.globalPos())
        menu.deleteLater()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        def rounded(rect, radius, fill, edge):
            p.setPen(QPen(QColor(edge), .9))
            p.setBrush(fill if isinstance(fill,QBrush) else QColor(fill))
            p.drawRoundedRect(rect,radius,radius)
        def line(a,b,color,width=1):
            p.setPen(QPen(QColor(color),width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            p.drawLine(a,b)
        def ellipse(rect, fill, edge):
            p.setPen(QPen(QColor(edge),.9))
            p.setBrush(fill if isinstance(fill,QBrush) else QColor(fill))
            p.drawEllipse(rect)

        # Shallow top lip keeps both physical keys visible in a front elevation.
        rounded(QRectF(4,11,192,193),12,gradient(0,12,0,204,[(0,"#f7f1df"),(.08,"#dbd4c2"),(.92,"#e8dfcb"),(1,"#b7ae9f")]),"#958e81")
        rounded(QRectF(6,20,188,181),10,gradient(10,22,186,199,[(0,"#f4efdf"),(.62,"#e9e1cf"),(1,"#d7cdb9")]),"#d0c6b1")
        for rect, colors, name in [(GREEN,("#62877a","#355e50","#24493e"),"toggle"),
                                   (ORANGE,("#eeaa74","#d88448","#99502c"),"reset")]:
            down = self.pressed == name
            rounded(rect.translated(0,1.5),4,colors[2],colors[2])
            rounded(rect.translated(0,1 if down else 0),4,gradient(0,4,0,20,[(0,colors[0]),(1,colors[1])]),colors[2])
        # Small molded symbols, placed on the actual controls.
        if self.deadline is None:
            path=QPainterPath(QPointF(65,9)); path.lineTo(65,17); path.lineTo(72,13); path.closeSubpath()
            p.fillPath(path,QColor("#eee9ce"))
        else:
            for x in (65,71): line(QPointF(x,9),QPointF(x,17),"#eee9ce",2)
        p.setPen(QPen(QColor("#583b29"),1.4)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(155,9,8,8),110*16,-300*16)
        line(QPointF(155,9),QPointF(155,12),"#583b29")
        line(QPointF(155,12),QPointF(158,12),"#583b29")
        ellipse(QRectF(12,26,176,176),gradient(40,30,160,196,[(0,"#aaa08d"),(.5,"#f9f4e7"),(1,"#cec3ab")]),"#d3c9b6")
        ellipse(QRectF(15,29,170,170),gradient(40,35,140,185,[(0,"#e8e6dd"),(.3,"#f8f4e9"),(1,"#ebe8df")]),"#aba697")
        sweep=self.shown/LIMIT*360
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient(48,52,146,164,[(0,"#416c59"),(1,"#204a3b")]))
        p.drawPie(QRectF(37,51,126,126),90*16,-round(sweep*16))
        p.setFont(QFont("Segoe UI",7,QFont.Weight.DemiBold))
        for i in range(60):
            angle=i*math.tau/60
            major=i%5==0
            line(circle_point(angle,82),circle_point(angle,77 if major else 80),"#46483e" if major else "#898778",1.25 if major else .75)
            if major:
                c=circle_point(angle,71.5)
                p.setPen(QColor("#3c423a"))
                p.drawText(QRectF(c.x()-9,c.y()-7,18,14),Qt.AlignmentFlag.AlignCenter,str(i))
        # A small inset readout remains legible even over the moving sector.
        rounded(QRectF(77,146,46,15),5,"#f1ebd9","#c8bfa9")
        p.setFont(QFont("Consolas",8,QFont.Weight.Bold))
        p.setPen(QColor("#34463a"))
        p.drawText(QRectF(76,145,48,17),Qt.AlignmentFlag.AlignCenter,
                   f"{self.remaining//60:02d}:{self.remaining%60:02d}")
        shadow=QRadialGradient(CENTER+QPointF(-3,4),25)
        shadow.setColorAt(0,QColor(43,30,18,125));shadow.setColorAt(1,QColor(43,30,18,0))
        p.setBrush(shadow);p.setPen(Qt.PenStyle.NoPen);p.drawEllipse(CENTER+QPointF(-3,4),25,25)
        ellipse(QRectF(82.5,96.5,35,35),gradient(83,97,115,132,[(0,"#efd2a1"),(.52,"#bb966a"),(1,"#876544")]),
                "#407c63" if self.armed else "#8c795f")
        for i in range(32):
            angle=i*math.tau/32+math.radians(sweep)
            line(circle_point(angle,15),circle_point(angle,16.4),"#9c805e",.7)
        ellipse(QRectF(85.5,99.5,29,29),gradient(85,99,113,128,[(0,"#e9cca0"),(.55,"#d6b285"),(1,"#c7a179")]),"#c3a071")
        angle=math.radians(sweep)
        line(circle_point(angle,7),circle_point(angle,12),"#92744f",1.8)
        p.end()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DialTimer()
    w.show()
    sys.exit(app.exec())
