from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import QTimer, QRectF, Qt
import pyavtools.fix as fix

class Historic_LinePlot(QWidget):
    def __init__(self, parent=None):
        super(Historic_LinePlot, self).__init__(parent)
        self.rows = 0
        self.cols = 0
        self.maxpens = 0
        self.maxnumvals = 0
        self.pens = []
        self.data = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

    def configure(self, config):
        self.rows = config.get("rows", 0)
        self.cols = config.get("cols", 0)
        self.maxpens = config.get("maxpens", 0)
        self.maxnumvals = config.get("maxnumvals", 0)
        for i in range(self.maxpens):
            pen_config = config.get(f"pen{i}", {})
            pen = {
                "name": pen_config.get("name", ""),
                "height": pen_config.get("height", 0),
                "dbkey": pen_config.get("dbkey", ""),
                "color": pen_config.get("color", "#FFFFFF"),
                "thk": pen_config.get("thk", 1),
                "miny": pen_config.get("miny", 0),
                "maxy": pen_config.get("maxy", 100),
                "limity": pen_config.get("limity", None),
            }
            self.pens.append(pen)
            self.data[pen["dbkey"]] = []

    def update_data(self):
        for pen in self.pens:
            item = fix.db.get_item(pen["dbkey"])
            value = item.value
            if len(self.data[pen["dbkey"]]) >= self.maxnumvals:
                self.data[pen["dbkey"]].pop(0)
            self.data[pen["dbkey"]].append(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        # Draw pen names
        pen_width = self.width() / self.maxpens
        for i, pen in enumerate(self.pens):
            painter.setPen(QColor(pen["color"]))
            font = QFont()
            font.setPixelSize(pen["height"])
            painter.setFont(font)
            text_rect = QRectF(i * pen_width, 0, pen_width, pen["height"])
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, pen["name"])

        # Draw line plots
        plot_height = self.height() - pen["height"]
        for pen in self.pens:
            painter.setPen(QPen(QColor(pen["color"]), pen["thk"]))
            for j in range(1, len(self.data[pen["dbkey"]])):
                x1 = (j - 1) * (self.width() / self.maxnumvals)
                y1 = plot_height - ((self.data[pen["dbkey"]][j - 1] - pen["miny"]) / (pen["maxy"] - pen["miny"]) * plot_height)
                x2 = j * (self.width() / self.maxnumvals)
                y2 = plot_height - ((self.data[pen["dbkey"]][j] - pen["miny"]) / (pen["maxy"] - pen["miny"]) * plot_height)
                painter.drawLine(x1, y1, x2, y2)

            if pen["limity"] is not None:
                painter.setPen(QPen(Qt.GlobalColor.white, pen["thk"], Qt.PenStyle.DashLine))
                y = plot_height - ((pen["limity"] - pen["miny"]) / (pen["maxy"] - pen["miny"]) * plot_height)
                painter.drawLine(0, y, self.width(), y)

        painter.end()
