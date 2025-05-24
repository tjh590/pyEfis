import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from pyefis.instruments.gauges.Historic_LinePlot import Historic_LinePlot
import pyavtools.fix as fix

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

def test_historic_line_plot_initialization(app, qtbot):
    widget = Historic_LinePlot()
    qtbot.addWidget(widget)
    assert widget.rows == 0
    assert widget.cols == 0
    assert widget.maxpens == 0
    assert widget.maxnumvals == 0
    assert widget.pens == []
    assert widget.data == {}

def test_historic_line_plot_configuration(app, qtbot):
    widget = Historic_LinePlot()
    qtbot.addWidget(widget)
    config = {
        "rows": 2,
        "cols": 3,
        "maxpens": 2,
        "maxnumvals": 10,
        "pen0": {
            "name": "Pen 1",
            "height": 12,
            "dbkey": "dbkey1",
            "color": "#FF0000",
            "thk": 2,
            "miny": 0,
            "maxy": 100,
            "limity": 50,
        },
        "pen1": {
            "name": "Pen 2",
            "height": 14,
            "dbkey": "dbkey2",
            "color": "#00FF00",
            "thk": 3,
            "miny": 10,
            "maxy": 90,
            "limity": 60,
        },
    }
    widget.configure(config)
    assert widget.rows == 2
    assert widget.cols == 3
    assert widget.maxpens == 2
    assert widget.maxnumvals == 10
    assert len(widget.pens) == 2
    assert widget.pens[0]["name"] == "Pen 1"
    assert widget.pens[1]["name"] == "Pen 2"
    assert widget.data["dbkey1"] == []
    assert widget.data["dbkey2"] == []

def test_historic_line_plot_update_data(app, qtbot):
    widget = Historic_LinePlot()
    qtbot.addWidget(widget)
    config = {
        "rows": 2,
        "cols": 3,
        "maxpens": 2,
        "maxnumvals": 10,
        "pen0": {
            "name": "Pen 1",
            "height": 12,
            "dbkey": "dbkey1",
            "color": "#FF0000",
            "thk": 2,
            "miny": 0,
            "maxy": 100,
            "limity": 50,
        },
        "pen1": {
            "name": "Pen 2",
            "height": 14,
            "dbkey": "dbkey2",
            "color": "#00FF00",
            "thk": 3,
            "miny": 10,
            "maxy": 90,
            "limity": 60,
        },
    }
    widget.configure(config)
    fix.db.get_item = lambda dbkey: type("MockItem", (object,), {"value": 42})()
    widget.update_data()
    assert widget.data["dbkey1"] == [42]
    assert widget.data["dbkey2"] == [42]

def test_historic_line_plot_paint_event(app, qtbot):
    widget = Historic_LinePlot()
    qtbot.addWidget(widget)
    config = {
        "rows": 2,
        "cols": 3,
        "maxpens": 2,
        "maxnumvals": 10,
        "pen0": {
            "name": "Pen 1",
            "height": 12,
            "dbkey": "dbkey1",
            "color": "#FF0000",
            "thk": 2,
            "miny": 0,
            "maxy": 100,
            "limity": 50,
        },
        "pen1": {
            "name": "Pen 2",
            "height": 14,
            "dbkey": "dbkey2",
            "color": "#00FF00",
            "thk": 3,
            "miny": 10,
            "maxy": 90,
            "limity": 60,
        },
    }
    widget.configure(config)
    fix.db.get_item = lambda dbkey: type("MockItem", (object,), {"value": 42})()
    widget.update_data()
    widget.resize(400, 300)
    widget.show()
    qtbot.waitExposed(widget)
    painter = QPainter(widget)
    widget.paintEvent(None)
    assert painter.isActive()
