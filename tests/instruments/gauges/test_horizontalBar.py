import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPen, QFont
from pyefis.instruments.gauges.horizontalBar import HorizontalBar
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_horizontal_bar_gauge(fix, qtbot):
    widget = HorizontalBar()
    assert widget.getRatio() == 2
    widget.setDbkey("NUM")
    widget.setupGauge()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.resizeEvent(None)
    # Font sizing behavior
    with track_calls(QFont, ["setPointSizeF", "setPixelSize"]) as tracker:
        widget.resizeEvent(None)
        assert tracker.was_not_called("setPointSizeF")
        widget.font_mask = "0000"
        widget.resizeEvent(None)
        assert tracker.was_called("setPointSizeF")
    widget.name_font_mask = "0000"
    widget.resizeEvent(None)
    widget.units_font_mask = "0000"
    widget.resizeEvent(None)

    # Ghost name alpha application
    widget.name = "TEST"
    with track_calls(type(widget.textColor), "setAlpha") as tracker:
        widget.name_font_ghost_mask = "0000"
        widget.update()
        qtbot.wait(50)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)

    # Ghost units alpha application
    widget.show_units = True
    widget.name_font_ghost_mask = None
    widget.name_font_mask = None
    widget.font_mask = None
    with track_calls(type(widget.textColor), "setAlpha") as tracker:
        widget.update()
        qtbot.wait(50)
        assert tracker.was_not_called("setAlpha")
        widget.units_font_ghost_mask = "0000"
        widget.update()
        qtbot.wait(50)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)

    # Ghost value alpha application
    widget.units_font_ghost_mask = None
    with track_calls(type(widget.valueColor), "setAlpha") as tracker:
        widget.update()
        qtbot.wait(50)
        assert tracker.was_not_called("setAlpha")
        widget.font_ghost_mask = "0000"
        widget.update()
        qtbot.wait(50)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)

    # Segments drawing color
    widget.setDbkey("NUMOK")
    widget.setupGauge()
    widget.update()
    qtbot.wait(50)
    widget.segments = 28
    with track_calls(QPen, "setColor") as tracker:
        widget.update()
        qtbot.wait(50)
        assert tracker.was_called_with("setColor", QColor(Qt.GlobalColor.black))
