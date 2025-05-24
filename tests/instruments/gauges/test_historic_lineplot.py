import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import Qt, QRectF
import pyavtools.fix as fix
from src.pyefis.instruments.gauges.Historic_LinePlot import HistoricLinePlot
import unittest

class TestHistoricLinePlot(unittest.TestCase):

    def setUp(self):
        self.app = QApplication(sys.argv)
        self.config = {
            "rows": 1,
            "cols": 1,
            "maxpens": 2,
            "maxnumvals": 60,
            "pens": [
                {"name": "Pen1", "height": 20, "dbkey": "key1", "color": "red", "thk": 2, "miny": 0, "maxy": 100, "limity": 80},
                {"name": "Pen2", "height": 20, "dbkey": "key2", "color": "blue", "thk": 2, "miny": 0, "maxy": 100}
            ]
        }
        self.widget = HistoricLinePlot(self.config)

    def test_initialization(self):
        self.assertEqual(self.widget.rows, 1)
        self.assertEqual(self.widget.cols, 1)
        self.assertEqual(self.widget.maxpens, 2)
        self.assertEqual(self.widget.maxnumvals, 60)
        self.assertEqual(len(self.widget.pens), 2)
        self.assertEqual(self.widget.pens[0]["name"], "Pen1")
        self.assertEqual(self.widget.pens[1]["name"], "Pen2")

    def test_draw_pen_names(self):
        painter = QPainter(self.widget)
        self.widget.draw_pen_names(painter)
        # Add assertions to verify the pen names are drawn correctly

    def test_draw_line_plots(self):
        painter = QPainter(self.widget)
        self.widget.draw_line_plots(painter)
        # Add assertions to verify the line plots are drawn correctly

    def test_update_data(self):
        self.widget.update_data()
        # Add assertions to verify the data is read from the FIX database and the line plots are updated

if __name__ == "__main__":
    unittest.main()
