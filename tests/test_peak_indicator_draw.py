import pytest
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import QRectF

from pyefis.instruments.gauges.horizontalBarSimple import HorizontalBarSimple
from pyefis.instruments.gauges.verticalBarSimple import VerticalBarSimple


def _make_image(w=50, h=50, fill=QColor(0, 0, 0, 255)):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(fill)
    return img


def _count_color(img: QImage, color: QColor) -> int:
    target = color.rgba()
    count = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixel(x, y) == target:
                count += 1
    return count

@pytest.mark.parametrize("supports_peak, peak_mode, peak_value, expect_draw", [
    (True, True, 80, True),            # normal draw
    (False, True, 80, False),          # supportsPeak disabled
    (True, False, 80, False),          # peakMode disabled
    (True, True, None, False),         # missing peakValue
])
def test_horizontal_peak_basic_conditions(supports_peak, peak_mode, peak_value, expect_draw):
    g = HorizontalBarSimple()
    # Core ranges
    g.lowRange = 0
    g.highRange = 100
    g.supportsPeak = supports_peak
    g.peakMode = peak_mode
    g.peakValue = peak_value
    g.peakColor = QColor(255, 0, 255)  # magenta marker
    # Provide defaults that drawPeakIndicator inspects
    g.peak_indicator_thickness = 4
    g.peak_indicator_extent = 4
    img = _make_image(60, 30)
    painter = QPainter(img)
    try:
        g.drawPeakIndicator(painter, 'horizontal', QRectF(5, 10, 50, 10))
    finally:
        painter.end()
    magenta_pixels = _count_color(img, QColor(255, 0, 255))
    if expect_draw:
        assert magenta_pixels > 0, "Expected peak marker to draw magenta pixels"
    else:
        assert magenta_pixels == 0, "Did not expect peak marker drawing"


def test_horizontal_peak_thickness_and_extent():
    g = HorizontalBarSimple()
    g.lowRange = 0
    g.highRange = 100
    g.supportsPeak = True
    g.peakMode = True
    g.peakValue = 50
    g.peakColor = QColor(0, 255, 0)  # green marker
    g.peak_indicator_thickness = 6
    g.peak_indicator_extent = 8  # larger extent top/bottom
    img = _make_image(80, 40)
    painter = QPainter(img)
    try:
        g.drawPeakIndicator(painter, 'horizontal', QRectF(10, 15, 60, 10))
    finally:
        painter.end()
    green_pixels = _count_color(img, QColor(0, 255, 0))
    # Expect at least thickness * bar_height pixels (rough lower bound) but more due to extent
    assert green_pixels >= g.peak_indicator_thickness * 10, "Thickness lower bound not met"


def test_horizontal_peak_out_of_range_value_clamps():
    g = HorizontalBarSimple()
    g.lowRange = 0
    g.highRange = 100
    g.supportsPeak = True
    g.peakMode = True
    g.peakValue = 150  # beyond highRange
    g.peakColor = QColor(255, 255, 0)  # yellow
    img = _make_image(60, 30)
    painter = QPainter(img)
    try:
        g.drawPeakIndicator(painter, 'horizontal', QRectF(0, 5, 50, 10))
    finally:
        painter.end()
    yellow_pixels = _count_color(img, QColor(255, 255, 0))
    assert yellow_pixels > 0, "Out-of-range peakValue should still draw (clamped/mapped)"


def test_horizontal_peak_zero_dimension_no_draw():
    g = HorizontalBarSimple()
    g.lowRange = 0
    g.highRange = 100
    g.supportsPeak = True
    g.peakMode = True
    g.peakValue = 50
    g.peakColor = QColor(0, 0, 255)  # blue
    img = _make_image(40, 20)
    painter = QPainter(img)
    try:
        g.drawPeakIndicator(painter, 'horizontal', QRectF(5, 5, 0, 0))
    finally:
        painter.end()
    blue_pixels = _count_color(img, QColor(0, 0, 255))
    assert blue_pixels == 0, "Zero-size bar_rect should not draw marker"


def test_vertical_peak_draw_and_position():
    """Basic vertical orientation draw to ensure code path executes and color appears."""
    g = VerticalBarSimple()
    g.lowRange = 0
    g.highRange = 100
    g.supportsPeak = True
    g.peakMode = True
    g.peakValue = 25
    g.peakColor = QColor(0, 128, 255)  # cyan-ish
    g.peak_indicator_thickness = 5
    img = _make_image(30, 100)
    painter = QPainter(img)
    try:
        g.drawPeakIndicator(painter, 'vertical', QRectF(10, 10, 10, 80))
    finally:
        painter.end()
    cyan_pixels = _count_color(img, QColor(0, 128, 255))
    assert cyan_pixels > 0, "Expected vertical peak marker to draw"


def test_vertical_peak_out_of_range_low_maps():
    g = VerticalBarSimple()
    g.lowRange = 0
    g.highRange = 100
    g.supportsPeak = True
    g.peakMode = True
    g.peakValue = -20  # below lowRange
    g.peakColor = QColor(200, 0, 200)
    img = _make_image(30, 120)
    painter = QPainter(img)
    try:
        g.drawPeakIndicator(painter, 'vertical', QRectF(5, 20, 15, 80))
    finally:
        painter.end()
    purple_pixels = _count_color(img, QColor(200, 0, 200))
    assert purple_pixels > 0, "Below-range peakValue should map and draw"
