import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QTimer, QRectF
from pyefis.instruments.gauges.EGTCHT_Combo import EGTCHT_Combo
import pyavtools.fix as fix

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

def test_EGTCHT_Combo_config(app, qtbot):
    config = {
        "rows": 4,
        "cols": 2,
        "gappct": 0.05,
        "headpct": 0.1,
        "EGT": {
            "minlimit": 1000,
            "warnlimit": 1300,
            "maxlimit": 1600,
            "maxextendpct": 0.1,
            "dbkeys": ["EGT1", "EGT2", "EGT3", "EGT4"]
        },
        "CHT": {
            "minlimit": 300,
            "warnlimit": 400,
            "maxlimit": 500,
            "maxextendpct": 0.1,
            "dbkeys": ["CHT1", "CHT2", "CHT3", "CHT4"]
        }
    }
    widget = EGTCHT_Combo(config=config)
    assert widget.rows == 4
    assert widget.cols == 2
    assert widget.gappct == 0.05
    assert widget.headpct == 0.1
    assert widget.EGT["minlimit"] == 1000
    assert widget.EGT["warnlimit"] == 1300
    assert widget.EGT["maxlimit"] == 1600
    assert widget.EGT["maxextendpct"] == 0.1
    assert widget.EGT["dbkeys"] == ["EGT1", "EGT2", "EGT3", "EGT4"]
    assert widget.CHT["minlimit"] == 300
    assert widget.CHT["warnlimit"] == 400
    assert widget.CHT["maxlimit"] == 500
    assert widget.CHT["maxextendpct"] == 0.1
    assert widget.CHT["dbkeys"] == ["CHT1", "CHT2", "CHT3", "CHT4"]

def test_EGTCHT_Combo_data_structures(app, qtbot):
    config = {
        "rows": 4,
        "cols": 2,
        "gappct": 0.05,
        "headpct": 0.1,
        "EGT": {
            "minlimit": 1000,
            "warnlimit": 1300,
            "maxlimit": 1600,
            "maxextendpct": 0.1,
            "dbkeys": ["EGT1", "EGT2", "EGT3", "EGT4"]
        },
        "CHT": {
            "minlimit": 300,
            "warnlimit": 400,
            "maxlimit": 500,
            "maxextendpct": 0.1,
            "dbkeys": ["CHT1", "CHT2", "CHT3", "CHT4"]
        }
    }
    widget = EGTCHT_Combo(config=config)
    assert widget.egtdatavalues == [0, 0, 0, 0]
    assert widget.chtvalues == [0, 0, 0, 0]
    assert widget.egtdatamax == [0, 0, 0, 0]
    assert widget.chtmax == [0, 0, 0, 0]

def test_EGTCHT_Combo_visual_presentation(app, qtbot):
    config = {
        "rows": 4,
        "cols": 2,
        "gappct": 0.05,
        "headpct": 0.1,
        "EGT": {
            "minlimit": 1000,
            "warnlimit": 1300,
            "maxlimit": 1600,
            "maxextendpct": 0.1,
            "dbkeys": ["EGT1", "EGT2", "EGT3", "EGT4"]
        },
        "CHT": {
            "minlimit": 300,
            "warnlimit": 400,
            "maxlimit": 500,
            "maxextendpct": 0.1,
            "dbkeys": ["CHT1", "CHT2", "CHT3", "CHT4"]
        }
    }
    widget = EGTCHT_Combo(config=config)
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    qtbot.waitExposed(widget)
    painter = QPainter(widget)
    widget.paintEvent(None)
    assert painter.isActive()
    assert widget.isVisible()
    assert widget.width() == 400
    assert widget.height() == 300
