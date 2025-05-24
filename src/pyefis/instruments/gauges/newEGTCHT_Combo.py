from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
from PyQt6.QtCore import QTimer, QRectF, Qt
import pyavtools.fix as fix

class newEGTCHT_Combo(QWidget):
    def __init__(self, config, parent=None):
        super(newEGTCHT_Combo, self).__init__(parent)
        self.config = config
        self.rows = config["rows"]
        self.cols = config["cols"]
        self.gappct = config["gappct"]
        self.headpct = config["headpct"]
        self.EGT = config["EGT"]
        self.CHT = config["CHT"]
        self.egtdatavalues = [0] * len(self.EGT["dbkeys"])
        self.chtdatavalues = [0] * len(self.CHT["dbkeys"])
        self.maxegtvalues = [0] * len(self.EGT["dbkeys"])
        self.maxchtvalues = [0] * len(self.CHT["dbkeys"])
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateData)
        self.timer.start(1000)
        self.setMinimumSize(200, 200)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Qt.GlobalColor.black))
        vline_x = self.width() // 2
        painter.setPen(QPen(QColor(Qt.GlobalColor.gray), 1))
        painter.drawLine(vline_x, 0, vline_x, self.height())

        header_font = QFont("Arial", int(self.height() * self.headpct / 100))
        painter.setFont(header_font)
        painter.setPen(QColor(Qt.GlobalColor.white))
        painter.drawText(QRectF(0, 0, vline_x, self.height() * self.headpct / 100), Qt.AlignmentFlag.AlignCenter, "EGT")
        painter.drawText(QRectF(vline_x, 0, vline_x, self.height() * self.headpct / 100), Qt.AlignmentFlag.AlignCenter, "CHT")

        element_height = (self.height() * (1 - self.headpct / 100) - (len(self.EGT["dbkeys"]) - 1) * self.height() * self.gappct / 100) / len(self.EGT["dbkeys"])
        for i in range(len(self.EGT["dbkeys"])):
            self.drawElement(painter, vline_x, i, element_height, self.egtdatavalues[i], self.EGT, True)
            self.drawElement(painter, vline_x, i, element_height, self.chtdatavalues[i], self.CHT, False)

    def updateData(self):
        for i, dbkey in enumerate(self.EGT["dbkeys"]):
            item = fix.db.get_item(dbkey)
            self.egtdatavalues[i] = item.value
            if item.value > self.maxegtvalues[i]:
                self.maxegtvalues[i] = item.value

        for i, dbkey in enumerate(self.CHT["dbkeys"]):
            item = fix.db.get_item(dbkey)
            self.chtdatavalues[i] = item.value
            if item.value > self.maxchtvalues[i]:
                self.maxchtvalues[i] = item.value

        self.update()

    def drawElement(self, painter, vline_x, index, element_height, dataval, config, is_egt):
        minlimit = config["minlimit"]
        warnlimit = config["warnlimit"]
        maxlimit = config["maxlimit"]
        maxextendpct = config["maxextendpct"]
        maxrange = maxlimit + (maxextendpct * (maxlimit - minlimit))
        bar_length = (dataval - minlimit) / (maxrange - minlimit) * (vline_x if is_egt else self.width() - vline_x)

        y = self.height() * self.headpct / 100 + index * (element_height + self.height() * self.gappct / 100)
        bar_color = QColor(Qt.GlobalColor.green)
        if dataval >= warnlimit:
            bar_color = QColor(Qt.GlobalColor.orange)
        if dataval >= maxlimit:
            bar_color = QColor(Qt.GlobalColor.red)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bar_color)
        if is_egt:
            painter.drawRect(vline_x - bar_length, y, bar_length, element_height)
        else:
            painter.drawRect(vline_x, y, bar_length, element_height)

        if dataval >= maxlimit:
            painter.setPen(QColor(Qt.GlobalColor.white))
            painter.setFont(QFont("Arial", int(element_height * 0.5)))
            painter.drawText(QRectF(vline_x - bar_length if is_egt else vline_x + bar_length, y, bar_length, element_height), Qt.AlignmentFlag.AlignCenter, str(int(dataval)))

        maxdataval = self.maxegtvalues[index] if is_egt else self.maxchtvalues[index]
        maxdataval_pos = (maxdataval - minlimit) / (maxrange - minlimit) * (vline_x if is_egt else self.width() - vline_x)
        painter.setPen(QPen(bar_color, 1))
        if is_egt:
            painter.drawLine(vline_x - maxdataval_pos, y, vline_x - maxdataval_pos, y + element_height)
        else:
            painter.drawLine(vline_x + maxdataval_pos, y, vline_x + maxdataval_pos, y + element_height)

        painter.setPen(QPen(QColor(Qt.GlobalColor.red), 1))
        maxlimit_pos = (maxlimit - minlimit) / (maxrange - minlimit) * (vline_x if is_egt else self.width() - vline_x)
        if is_egt:
            painter.drawLine(vline_x - maxlimit_pos, y, vline_x - maxlimit_pos, y + element_height)
        else:
            painter.drawLine(vline_x + maxlimit_pos, y, vline_x + maxlimit_pos, y + element_height)
