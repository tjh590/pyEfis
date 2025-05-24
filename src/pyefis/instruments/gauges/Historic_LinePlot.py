import sys
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import QTimer, Qt, QRectF
import pyavtools.fix as fix

class HistoricLinePlot(QWidget):
    def __init__(self, config, parent=None):
        super(HistoricLinePlot, self).__init__(parent)
        self.config = config
        self.rows = config.get("rows", 1)
        self.cols = config.get("cols", 1)
        self.maxpens = config.get("maxpens", 1)
        self.maxnumvals = config.get("maxnumvals", 60)
        self.pens = config.get("pens", [])
        self.data = {pen["dbkey"]: [] for pen in self.pens}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        self.draw_pen_names(painter)
        self.draw_line_plots(painter)

    def draw_pen_names(self, painter):
        painter.setFont(QFont("Arial", 10))
        pen_width = self.width() / len(self.pens)
        for i, pen in enumerate(self.pens):
            painter.setPen(QColor(pen["color"]))
            text_rect = QRectF(i * pen_width, 0, pen_width, pen["height"])
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, pen["name"])

    def draw_line_plots(self, painter):
        plot_height = self.height() - self.pens[0]["height"]
        for pen in self.pens:
            painter.setPen(QPen(QColor(pen["color"]), pen["thk"]))
            data = self.data[pen["dbkey"]]
            if not data:
                continue
            x_step = self.width() / self.maxnumvals
            for i in range(1, len(data)):
                x1 = (i - 1) * x_step
                y1 = plot_height - (data[i - 1] - pen["miny"]) / (pen["maxy"] - pen["miny"]) * plot_height
                x2 = i * x_step
                y2 = plot_height - (data[i] - pen["miny"]) / (pen["maxy"] - pen["miny"]) * plot_height
                painter.drawLine(x1, y1, x2, y2)
            if "limity" in pen:
                limit_y = plot_height - (pen["limity"] - pen["miny"]) / (pen["maxy"] - pen["miny"]) * plot_height
                painter.setPen(QPen(Qt.GlobalColor.white, 2, Qt.PenStyle.DashLine))
                painter.drawLine(0, limit_y, self.width(), limit_y)

    def update_data(self):
        for pen in self.pens:
            dbkey = pen["dbkey"]
            item = fix.db.get_item(dbkey)
            value = item.value
            if len(self.data[dbkey]) >= self.maxnumvals:
                self.data[dbkey].pop(0)
            self.data[dbkey].append(value)
            if "limity" in pen and value > pen["limity"]:
                pen["exceeded"] = True
            else:
                pen["exceeded"] = False
        self.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    config = {
        "rows": 1,
        "cols": 1,
        "maxpens": 2,
        "maxnumvals": 60,
        "pens": [
            {"name": "Pen1", "height": 20, "dbkey": "key1", "color": "red", "thk": 2, "miny": 0, "maxy": 100, "limity": 80},
            {"name": "Pen2", "height": 20, "dbkey": "key2", "color": "blue", "thk": 2, "miny": 0, "maxy": 100}
        ]
    }
    widget = HistoricLinePlot(config)
    widget.show()
    sys.exit(app.exec())
