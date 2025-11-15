import pytest
import os
from unittest import mock
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, qRound
from PyQt6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPaintEvent, QFontMetrics
from PyQt6 import QtGui
from pyefis.instruments.ai.VirtualVfr import VirtualVfr
import pyefis.hmi as hmi
from tests.utils import track_calls

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_virtual_VFR(fix,qtbot):
    # Ordered fallback lists
    dbpath_candidates = ["/path", "/CIFP"]
    indexpath_candidates = ["/indexpath", "/CIFP"]

    def first_existing(candidates):
        for c in candidates:
            if os.path.exists(os.path.expanduser(c)):
                return c
        # If none exist, just return the first so instrument still initializes
        return candidates[0]

    # Resolve candidates now (simulate runtime fallback)
    resolved_dbpath = first_existing(dbpath_candidates)
    resolved_indexpath = first_existing(indexpath_candidates)

    def data_values(arg):
        if arg == 'metadata':
            return None
        elif arg == 'dbpath':
            return resolved_dbpath
        elif arg == 'indexpath':
            return resolved_indexpath
        elif arg == 'refresh_period':
            return 0.1
        return None

    widget = VirtualVfr()
    widget.myparent = mock.MagicMock()
    widget.myparent.get_config_item = data_values
    qtbot.addWidget(widget)
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    # Allow some time for POV init/render; shorter than original 3000ms while sufficient
    qtbot.wait(500)
