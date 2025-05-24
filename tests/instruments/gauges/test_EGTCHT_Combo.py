import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPen, QPainter, QRectF
from pyefis.instruments.gauges.EGTCHT_Combo import EGTCHT_Combo
import pyavtools.fix as fix

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

def test_egtcht_combo_config(app, qtbot):
    config = {
        'rows': 4,
        'cols': 2,
        'gappct': 0.05,
        'headpct': 0.1,
        'EGT': {
            'minlimit': 1000,
            'warnlimit': 1300,
            'maxlimit': 1600,
            'maxextendpct': 0.1,
            'dbkeys': ["EGT1", "EGT2", "EGT3", "EGT4"]
        },
        'CHT': {
            'minlimit': 300,
            'warnlimit': 400,
            'maxlimit': 500,
            'maxextendpct': 0.1,
            'dbkeys': ["CHT1", "CHT2", "CHT3", "CHT4"]
        }
    }
    widget = EGTCHT_Combo(config=config)
    qtbot.addWidget(widget)
    assert widget.config == config
    assert widget.rows == 4
    assert widget.cols == 2
    assert widget.gappct == 0.05
    assert widget.headpct == 0.1
    assert widget.egts_dbkeys == ["EGT1", "EGT2", "EGT3", "EGT4"]
    assert widget.chts_dbkeys == ["CHT1", "CHT2", "CHT3", "CHT4"]
    assert widget.egts_minlimit == 1000
    assert widget.chts_minlimit == 300
    assert widget.egts_warnlimit == 1300
    assert widget.chts_warnlimit == 400
    assert widget.egts_maxlimit == 1600
    assert widget.chts_maxlimit == 500
    assert widget.egts_maxextendpct == 0.1
    assert widget.chts_maxextendpct == 0.1

def test_egtcht_combo_visual(app, qtbot):
    config = {
        'rows': 4,
        'cols': 2,
        'gappct': 0.05,
        'headpct': 0.1,
        'EGT': {
            'minlimit': 1000,
            'warnlimit': 1300,
            'maxlimit': 1600,
            'maxextendpct': 0.1,
            'dbkeys': ["EGT1", "EGT2", "EGT3", "EGT4"]
        },
        'CHT': {
            'minlimit': 300,
            'warnlimit': 400,
            'maxlimit': 500,
            'maxextendpct': 0.1,
            'dbkeys': ["CHT1", "CHT2", "CHT3", "CHT4"]
        }
    }
    widget = EGTCHT_Combo(config=config)
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    qtbot.waitExposed(widget)
    painter = QPainter(widget)
    widget.draw_background(painter)
    widget.draw_labels(painter)
    widget.draw_egt_bars(painter)
    widget.draw_cht_bars(painter)
    assert widget.isVisible()

def test_egtcht_combo_data_update(app, qtbot):
    config = {
        'rows': 4,
        'cols': 2,
        'gappct': 0.05,
        'headpct': 0.1,
        'EGT': {
            'minlimit': 1000,
            'warnlimit': 1300,
            'maxlimit': 1600,
            'maxextendpct': 0.1,
            'dbkeys': ["EGT1", "EGT2", "EGT3", "EGT4"]
        },
        'CHT': {
            'minlimit': 300,
            'warnlimit': 400,
            'maxlimit': 500,
            'maxextendpct': 0.1,
            'dbkeys': ["CHT1", "CHT2", "CHT3", "CHT4"]
        }
    }
    widget = EGTCHT_Combo(config=config)
    qtbot.addWidget(widget)
    widget.init_dbkeys()
    widget.update_egt(1200, 0)
    assert widget.egts[0] == 1200
    assert widget.egts_max[0] == 1200
    assert widget.egts_warn[0] == False
    assert widget.egts_alarm[0] == False
    widget.update_egt(1400, 0)
    assert widget.egts[0] == 1400
    assert widget.egts_max[0] == 1400
    assert widget.egts_warn[0] == True
    assert widget.egts_alarm[0] == False
    widget.update_egt(1700, 0)
    assert widget.egts[0] == 1700
    assert widget.egts_max[0] == 1700
    assert widget.egts_warn[0] == True
    assert widget.egts_alarm[0] == True
    widget.update_cht(350, 0)
    assert widget.chts[0] == 350
    assert widget.chts_max[0] == 350
    assert widget.chts_warn[0] == False
    assert widget.chts_alarm[0] == False
    widget.update_cht(450, 0)
    assert widget.chts[0] == 450
    assert widget.chts_max[0] == 450
    assert widget.chts_warn[0] == True
    assert widget.chts_alarm[0] == False
    widget.update_cht(550, 0)
    assert widget.chts[0] == 550
    assert widget.chts_max[0] == 550
    assert widget.chts_warn[0] == True
    assert widget.chts_alarm[0] == True
    widget.update_data()
    assert widget.egts[0] == 1700
    assert widget.chts[0] == 550
