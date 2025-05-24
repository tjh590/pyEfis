import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QFont, QPen, QTimer, QRectF
from pyefis.instruments.gauges.newEGTCHT_Combo import newEGTCHT_Combo
import pyavtools.fix as fix

class TestNewEGTCHT_Combo(unittest.TestCase):
    def setUp(self):
        self.app = QApplication([])
        self.config = {
            "rows": 2,
            "cols": 2,
            "gappct": 5,
            "headpct": 10,
            "EGT": {
                "minlimit": 100,
                "warnlimit": 500,
                "maxlimit": 1000,
                "maxextendpct": 0.1,
                "dbkeys": ["EGT1", "EGT2"]
            },
            "CHT": {
                "minlimit": 50,
                "warnlimit": 300,
                "maxlimit": 600,
                "maxextendpct": 0.1,
                "dbkeys": ["CHT1", "CHT2"]
            }
        }
        self.widget = newEGTCHT_Combo(self.config)

    def test_initialization(self):
        self.assertEqual(self.widget.rows, 2)
        self.assertEqual(self.widget.cols, 2)
        self.assertEqual(self.widget.gappct, 5)
        self.assertEqual(self.widget.headpct, 10)
        self.assertEqual(self.widget.EGT["minlimit"], 100)
        self.assertEqual(self.widget.CHT["minlimit"], 50)
        self.assertEqual(len(self.widget.egtdatavalues), 2)
        self.assertEqual(len(self.widget.chtdatavalues), 2)

    def test_updateData(self):
        fix.db.get_item = lambda dbkey: mock.Mock(value=200)
        self.widget.updateData()
        self.assertEqual(self.widget.egtdatavalues, [200, 200])
        self.assertEqual(self.widget.chtdatavalues, [200, 200])

    def test_paintEvent(self):
        self.widget.resize(400, 400)
        self.widget.show()
        self.widget.paintEvent(None)
        self.assertTrue(self.widget.isVisible())
