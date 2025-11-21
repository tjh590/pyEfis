import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from pyefis.instruments import gauges

@pytest.fixture
def app(qtbot):
    inst = QApplication.instance()
    if inst is None:
        inst = QApplication([])
    return inst


def make_vertical():
    w = gauges.VerticalBarImproved()
    w.setDbkey("NUMOK")
    w.setupGauge()
    w.lowRange = 0.0
    w.highRange = 100.0
    w.value = 10.0
    w.resize(200, 300)
    return w


def test_peak_advances_when_enabled(fix, qtbot):
    w = make_vertical()
    qtbot.addWidget(w)
    w.peakMode = True
    start_peak = w.peakValue
    w.value = start_peak + 5.0
    assert w.peakValue == pytest.approx(start_peak + 5.0)


def test_peak_does_not_advance_when_disabled(fix, qtbot):
    w = make_vertical()
    qtbot.addWidget(w)
    w.peakMode = False
    base_peak = w.peakValue
    w.value = base_peak + 30.0
    # Peak should not move because mode disabled
    assert w.peakValue == base_peak


def test_peak_reset_sets_to_current_value(fix, qtbot):
    w = make_vertical()
    qtbot.addWidget(w)
    w.peakMode = True
    w.value = 55.0
    assert w.peakValue == 55.0
    w.value = 30.0  # Peak stays 55
    assert w.peakValue == 55.0
    w.resetPeak()
    assert w.peakValue == w.value == 30.0


def test_should_show_peak_delta_logic(fix, qtbot):
    w = make_vertical()
    qtbot.addWidget(w)
    w.peakMode = True
    w.peak_delta_threshold = 10.0
    # Raise peak to 70
    w.value = 70.0
    assert w.peakValue == 70.0
    # Current drops to 65: delta = -5 -> should not show
    w.value = 65.0
    assert w.shouldShowPeakDelta() is False
    # Drop further so delta <= -10
    w.value = 55.0
    assert w.shouldShowPeakDelta() is True

