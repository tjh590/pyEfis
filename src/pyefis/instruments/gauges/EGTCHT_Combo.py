from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QColor, QPainter, QFont, QPen
from PyQt6.QtCore import QTimer, QRectF, Qt
import pyavtools.fix as fix

class EGTCHT_Combo(QWidget):
    def __init__(self, parent=None, config=None):
        super(EGTCHT_Combo, self).__init__(parent)
        self.config = config
        self.egts = [0] * len(config['EGT']['dbkeys'])
        self.chts = [0] * len(config['CHT']['dbkeys'])
        self.egts_max = [0] * len(config['EGT']['dbkeys'])
        self.chts_max = [0] * len(config['CHT']['dbkeys'])
        self.egts_warn = [False] * len(config['EGT']['dbkeys'])
        self.chts_warn = [False] * len(config['CHT']['dbkeys'])
        self.egts_alarm = [False] * len(config['EGT']['dbkeys'])
        self.chts_alarm = [False] * len(config['CHT']['dbkeys'])
        self.egts_dbkeys = config['EGT']['dbkeys']
        self.chts_dbkeys = config['CHT']['dbkeys']
        self.egts_minlimit = config['EGT']['minlimit']
        self.chts_minlimit = config['CHT']['minlimit']
        self.egts_warnlimit = config['EGT']['warnlimit']
        self.chts_warnlimit = config['CHT']['warnlimit']
        self.egts_maxlimit = config['EGT']['maxlimit']
        self.chts_maxlimit = config['CHT']['maxlimit']
        self.egts_maxextendpct = config['EGT']['maxextendpct']
        self.chts_maxextendpct = config['CHT']['maxextendpct']
        self.rows = config['rows']
        self.cols = config['cols']
        self.gappct = config['gappct']
        self.headpct = config['headpct']
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)
        self.init_dbkeys()

    def init_dbkeys(self):
        for i, dbkey in enumerate(self.egts_dbkeys):
            item = fix.db.get_item(dbkey)
            item.valueChanged[float].connect(lambda value, idx=i: self.update_egt(value, idx))
        for i, dbkey in enumerate(self.chts_dbkeys):
            item = fix.db.get_item(dbkey)
            item.valueChanged[float].connect(lambda value, idx=i: self.update_cht(value, idx))

    def update_egt(self, value, idx):
        self.egts[idx] = value
        if value > self.egts_max[idx]:
            self.egts_max[idx] = value
        self.egts_warn[idx] = value >= self.egts_warnlimit
        self.egts_alarm[idx] = value >= self.egts_maxlimit
        self.update()

    def update_cht(self, value, idx):
        self.chts[idx] = value
        if value > self.chts_max[idx]:
            self.chts_max[idx] = value
        self.chts_warn[idx] = value >= self.chts_warnlimit
        self.chts_alarm[idx] = value >= self.chts_maxlimit
        self.update()

    def update_data(self):
        for i, dbkey in enumerate(self.egts_dbkeys):
            item = fix.db.get_item(dbkey)
            self.update_egt(item.value, i)
        for i, dbkey in enumerate(self.chts_dbkeys):
            item = fix.db.get_item(dbkey)
            self.update_cht(item.value, i)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.draw_background(painter)
        self.draw_labels(painter)
        self.draw_egt_bars(painter)
        self.draw_cht_bars(painter)

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
        painter.drawText(QRectF(0, 0, self.width() // 2, int(self.height() * self.headpct)), Qt.AlignmentFlag.AlignCenter, "EGT")
        painter.drawText(QRectF(self.width() // 2, 0, self.width() // 2, int(self.height() * self.headpct)), Qt.AlignmentFlag.AlignCenter, "CHT")

    def draw_egt_bars(self, painter):
        bar_height = (self.height() * (1 - self.headpct) - (len(self.egts) - 1) * self.height() * self.gappct) / len(self.egts)
        for i, value in enumerate(self.egts):
            y = int(self.height() * self.headpct + i * (bar_height + self.height() * self.gappct))
            self.draw_bar(painter, value, self.egts_max[i], self.egts_warn[i], self.egts_alarm[i], self.egts_minlimit, self.egts_maxlimit, self.egts_maxextendpct, 0, y, self.width() // 2, bar_height)

    def draw_cht_bars(self, painter):
        bar_height = (self.height() * (1 - self.headpct) - (len(self.chts) - 1) * self.height() * self.gappct) / len(self.chts)
        for i, value in enumerate(self.chts):
            y = int(self.height() * self.headpct + i * (bar_height + self.height() * self.gappct))
            self.draw_bar(painter, value, self.chts_max[i], self.chts_warn[i], self.chts_alarm[i], self.chts_minlimit, self.chts_maxlimit, self.chts_maxextendpct, self.width() // 2, y, self.width() // 2, bar_height)

    def draw_bar(self, painter, value, max_value, warn, alarm, minlimit, maxlimit, maxextendpct, x, y, width, height):
        bar_range = maxlimit + (maxextendpct * (maxlimit - minlimit)) - minlimit
        bar_length = (value - minlimit) / bar_range * width
        max_bar_length = (max_value - minlimit) / bar_range * width
        max_bar_length = min(max_bar_length, width)
        bar_length = min(bar_length, width)
        color = QColor(Qt.GlobalColor.green)
        if warn:
            color = QColor(Qt.GlobalColor.orange)
        if alarm:
            color = QColor(Qt.GlobalColor.red)
        painter.fillRect(QRectF(x, y, bar_length, height), color)
        painter.setPen(QColor(Qt.GlobalColor.red))
        painter.drawLine(x + max_bar_length, y, x + max_bar_length, y + height)
        if alarm:
            painter.setPen(QColor(Qt.GlobalColor.white))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(x + bar_length, y, width - bar_length, height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(int(value)))
        elif value < minlimit:
            painter.setPen(QColor(Qt.GlobalColor.white))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(x, y, width, height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(int(value)))
