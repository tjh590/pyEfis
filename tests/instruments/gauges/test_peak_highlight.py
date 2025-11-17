import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen, QPainter, QColor

from pyefis.instruments import gauges
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


# (class_attr, is_vertical, supports_peak, supports_highlight)
GAUGE_MATRIX = [
    ("HorizontalBar", False, False, False),
    ("HorizontalBarImproved", False, False, False),
    ("HorizontalBarSimple", False, True, False),
    ("VerticalBar", True, True, True),
    ("VerticalBarImproved", True, True, True),  # peak line expected; highlight expected
    ("VerticalBarSimple", True, True, True),
]


def _make_widget(class_name):
    cls = getattr(gauges, class_name)
    w = cls()
    # Basic setup consistent with other tests
    w.setDbkey("NUMOK")
    w.setupGauge()
    w.resize(300, 200)
    # Establish sane ranges for mapping
    w.lowRange = 0.0
    w.highRange = 100.0
    # Put value in mid range
    w.value = 40.0
    return w


@pytest.mark.parametrize("class_name,is_vertical,supports_highlight", [
    (name, is_vert, supports_h)
    for (name, is_vert, _supports_peak, supports_h) in GAUGE_MATRIX
])
def test_highlight_ball_toggle_draws_ellipse(fix, qtbot, class_name, is_vertical, supports_highlight):
    widget = _make_widget(class_name)
    qtbot.addWidget(widget)
    # Force a default layout pass
    widget.resizeEvent(None)

    # Ensure highlight True and not overridden in paintEvent
    widget.highlight_key = None
    widget.highlight = True

    with track_calls(QPainter, "drawEllipse") as tracker:
        widget.paintEvent(None)
        if supports_highlight and is_vertical:
            assert tracker.was_called("drawEllipse"), f"Expected highlight ellipse for {class_name}"
        else:
            assert tracker.was_not_called("drawEllipse"), f"Did not expect highlight ellipse for {class_name}"


@pytest.mark.parametrize("class_name,supports_peak", [
    (name, supports_p)
    for (name, _is_vert, supports_p, _supports_h) in GAUGE_MATRIX
])
def test_peak_mode_sets_peak_brush(fix, qtbot, class_name, supports_peak):
    widget = _make_widget(class_name)
    qtbot.addWidget(widget)
    # Provide a unique peak color and enable peak mode
    sentinel = QColor(123, 45, 67)
    # Horizontal bars may not define peakColor; set regardless
    setattr(widget, "peakColor", sentinel)
    widget.peakMode = True
    widget.peakValue = 60.0
    widget.value = 55.0
    widget.resizeEvent(None)

    with track_calls(QPainter, "setBrush") as tracker:
        widget.paintEvent(None)
        # Inspect all setBrush calls for a QBrush using our sentinel color
        seen_peak_brush = False
        for (_method, args, _kwargs) in tracker.calls:
            if len(args) == 1:
                obj = args[0]
                try:
                    # If it's a QBrush, compare its color
                    if hasattr(obj, "color") and callable(getattr(obj, "color")):
                        if obj.color() == sentinel:
                            seen_peak_brush = True
                            break
                    # If it's a QColor, compare directly
                    if isinstance(obj, QColor) and obj == sentinel:
                        seen_peak_brush = True
                        break
                except Exception:
                    pass
        if supports_peak:
            assert seen_peak_brush, f"Expected peak brush set for {class_name}"
        else:
            assert not seen_peak_brush, f"Did not expect peak brush for {class_name}"
