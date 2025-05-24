from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
import pyavtools.fix as fix

class EGTCHT_Combo(QWidget):
    def __init__(self, parent=None, config=None):
        super(EGTCHT_Combo, self).__init__(parent)
        self.config = config
        self.rows = config.get("rows", 1)
        self.cols = config.get("cols", 1)
        self.gappct = config.get("gappct", 0.05)
        self.headpct = config.get("headpct", 0.1)
        self.EGT = config.get("EGT", {})
        self.CHT = config.get("CHT", {})
        self.egtdatavalues = [0] * len(self.EGT.get("dbkeys", []))
        self.chtvalues = [0] * len(self.CHT.get("dbkeys", []))
        self.egtdatamax = [0] * len(self.EGT.get("dbkeys", []))
        self.chtmax = [0] * len(self.CHT.get("dbkeys", []))
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(1000)

    def update_data(self):
        for i, dbkey in enumerate(self.EGT.get("dbkeys", [])):
            item = fix.db.get_item(dbkey)
            self.egtdatavalues[i] = item.value
            if item.value > self.egtdatamax[i]:
                self.egtdatamax[i] = item.value
        for i, dbkey in enumerate(self.CHT.get("dbkeys", [])):
            item = fix.db.get_item(dbkey)
            self.chtvalues[i] = item.value
            if item.value > self.chtmax[i]:
                self.chtmax[i] = item.value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.draw_background(painter)
        self.draw_labels(painter)
        self.draw_data(painter)

    def draw_background(self, painter):
        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.black))
        pen = QPen(QColor(Qt.GlobalColor.gray))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(self.width() // 2, 0, self.width() // 2, self.height())

    def draw_labels(self, painter):
        font = QFont()
        font.setPixelSize(int(self.height() * self.headpct))
        painter.setFont(font)
        painter.setPen(QColor(Qt.GlobalColor.white))
        painter.drawText(QRectF(0, 0, self.width() // 2, self.height() * self.headpct), Qt.AlignmentFlag.AlignCenter, "EGT")
        painter.drawText(QRectF(self.width() // 2, 0, self.width() // 2, self.height() * self.headpct), Qt.AlignmentFlag.AlignCenter, "CHT")

    def draw_data(self, painter):
        element_height = (self.height() * (1 - self.headpct) - (len(self.egtdatavalues) - 1) * self.height() * self.gappct) / len(self.egtdatavalues)
        for i, value in enumerate(self.egtdatavalues):
            self.draw_element(painter, value, self.egtdatamax[i], self.EGT, i, True, element_height)
        for i, value in enumerate(self.chtvalues):
            self.draw_element(painter, value, self.chtmax[i], self.CHT, i, False, element_height)

    def draw_element(self, painter, value, maxvalue, config, index, is_egt, element_height):
        minlimit = config.get("minlimit", 0)
        warnlimit = config.get("warnlimit", 0)
        maxlimit = config.get("maxlimit", 0)
        maxextendpct = config.get("maxextendpct", 0)
        bar_range = maxlimit + (maxextendpct * (maxlimit - minlimit)) - minlimit
        bar_length = (value - minlimit) / bar_range * (self.width() // 2)
        maxbar_length = (maxvalue - minlimit) / bar_range * (self.width() // 2)
        y = self.height() * self.headpct + index * (element_height + self.height() * self.gappct)
        if is_egt:
            x = self.width() // 2 - bar_length
            maxx = self.width() // 2 - maxbar_length
            textx = self.width() // 2 - bar_length - 20
        else:
            x = self.width() // 2
            maxx = self.width() // 2 + maxbar_length
            textx = self.width() // 2 + bar_length + 20

        if value < minlimit:
            color = QColor(Qt.GlobalColor.white)
            if any(v > minlimit for v in (self.egtdatavalues if is_egt else self.chtvalues)):
                color = QColor(Qt.GlobalColor.red)
            painter.setPen(color)
            painter.drawText(QRectF(textx, y, 40, element_height), Qt.AlignmentFlag.AlignCenter, str(int(value)))
        else:
            if value >= maxlimit:
                color = QColor(Qt.GlobalColor.red)
                painter.setPen(QColor(Qt.GlobalColor.white))
                painter.drawText(QRectF(textx, y, 40, element_height), Qt.AlignmentFlag.AlignCenter, str(int(value)))
            elif value >= warnlimit:
                color = QColor(Qt.GlobalColor.orange)
            else:
                color = QColor(Qt.GlobalColor.green)
            painter.setBrush(color)
            painter.drawRect(QRectF(x, y, bar_length, element_height))

        painter.setPen(QColor(Qt.GlobalColor.red))
        painter.drawLine(maxx, y, maxx, y + element_height)
        painter.setPen(color)
        painter.drawLine(self.width() // 2, y, self.width() // 2, y + element_height)
