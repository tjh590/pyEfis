import os
import pytest
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import Qt

from pyefis.instruments.gauges.horizontalBarSimple import HorizontalBarSimple
from pyefis.instruments.gauges.verticalBarSimple import VerticalBarSimple


def _render(widget, w, h, qtbot):
    widget.resize(w, h)
    widget.show()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    widget.render(p)
    p.end()
    return img


def _approx_eq(c1, c2, tol=5):
    return (
        abs(c1.red() - c2.red()) <= tol and
        abs(c1.green() - c2.green()) <= tol and
        abs(c1.blue() - c2.blue()) <= tol
    )


@pytest.mark.parametrize("cls, orient", [
    (HorizontalBarSimple, "h"),
    (VerticalBarSimple, "v"),
])
@pytest.mark.parametrize("thresholds,value,expect", [
    ({"lowAlarm":50, "lowWarn":85, "highWarn":200, "highAlarm":230, "lowRange":0, "highRange":300}, 40, "alarm"),
    ({"lowAlarm":50, "lowWarn":85, "highWarn":200, "highAlarm":230, "lowRange":0, "highRange":300}, 80, "warn"),
    ({"lowAlarm":50, "lowWarn":85, "highWarn":200, "highAlarm":230, "lowRange":0, "highRange":300}, 150, "safe"),
    ({"lowAlarm":50, "lowWarn":85, "highWarn":200, "highAlarm":230, "lowRange":0, "highRange":300}, 210, "highwarn"),
    ({"lowAlarm":50, "lowWarn":85, "highWarn":200, "highAlarm":230, "lowRange":0, "highRange":300}, 240, "alarm"),
])
def test_bar_simple_colors(tmp_path, qtbot, fix, cls, orient, thresholds, value, expect):
    w = cls()
    w.setDbkey("TEST")
    w.setupGauge()
    # apply thresholds and value
    for k, v in thresholds.items():
        setattr(w, k, v)
    w._value = value

    # Render and sample pixels along the bar centerline
    width, height = (300, 180) if orient == "h" else (180, 240)
    img = _render(w, width, height, qtbot)

    # Expected colors from widget
    safe = w.safeColor
    warn = w.warnColor
    alarm = w.alarmColor

    # Sample strategy: 
    # - horizontal: sample middle row at 25%, 60%, 90% along width
    # - vertical: sample middle column at 10%, 40%, 80% along height
    if orient == "h":
        y = height // 2
        xs = [int(width*0.25), int(width*0.60), int(width*0.90)]
        samples = [img.pixelColor(x, y) for x in xs]
    else:
        x = width // 2
        ys = [int(height*0.10), int(height*0.40), int(height*0.80)]
        samples = [img.pixelColor(x, y) for y in ys]

    if expect == "alarm":
        assert all(_approx_eq(c, alarm) for c in samples)
    elif expect == "warn":
        assert all(_approx_eq(c, warn) for c in samples)
    elif expect == "safe":
        assert all(_approx_eq(c, safe) for c in samples)
    elif expect == "highwarn":
        # In high-warn, there should be at least one warn-colored sample;
        # the rest may be safe depending on band placement
        assert any(_approx_eq(c, warn) for c in samples)
        assert any(_approx_eq(c, safe) for c in samples)
    else:
        pytest.fail("unexpected expect key")

    # Always emit PNGs for debugging into test_results (requested)
    out_dir = os.path.join("extras", "extras", "test_results")
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"{cls.__name__}_{orient}_v{value}.png"
    img.save(os.path.join(out_dir, out_name))
