import os
import yaml
import importlib
import pytest
from typing import Dict, Any
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import Qt


@pytest.fixture
def app(qtbot):
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_SCALE_FACTOR", "1")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    return app


def _render_widget_png(widget, w: int, h: int, out_path: str, qtbot):
    widget.resize(w, h)
    widget.show()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    widget.render(p)
    p.end()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)


def _make_widget(class_path: str):
    mod_name, cls_name = class_path.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls()


def _apply_thresholds(widget, thresholds: Dict[str, Any]):
    for k, v in (thresholds or {}).items():
        setattr(widget, k, v)


@pytest.mark.screenshots
def test_generate_bar_screenshots(fix, qtbot, request):
    root = request.config.rootdir
    scenarios_path = os.getenv(
        "BARS_SCENARIOS_YAML",
        os.path.join(root, "tests/screenshots/configs/bar_scenarios.yaml"),
    )
    assert os.path.exists(scenarios_path), f"Scenario YAML not found: {scenarios_path}"
    with open(scenarios_path) as f:
        data = yaml.safe_load(f) or {}

    out_dir = data.get("outDir") or os.path.join(root, "extras/extras/test_results")
    scenarios = data.get("scenarios", [])

    for sc in scenarios:
        cls_path = sc.get("class", "pyefis.instruments.gauges.VerticalBarSimple")
        name = sc.get("name", cls_path.split('.')[-1])
        w = int(sc.get("size", {}).get("w", 300))
        h = int(sc.get("size", {}).get("h", 200))
        thresholds = sc.get("thresholds", {})
        value = sc.get("value")

        widget = _make_widget(cls_path)
        widget.setDbkey("TEST")
        widget.setupGauge()
        _apply_thresholds(widget, thresholds)
        if value is not None:
            widget._value = value
        out_path = os.path.join(out_dir, f"{name}.png")
        _render_widget_png(widget, w, h, out_path, qtbot)
