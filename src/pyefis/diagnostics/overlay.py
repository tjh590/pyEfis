from PyQt6.QtCore import QElapsedTimer, QTimer, QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont
import logging
import re

try:
    import pyavtools.fix as fix
except Exception:
    fix = None

class PaintStats:
    __slots__ = ("total_ns","count","max_ns")
    def __init__(self):
        self.total_ns = 0
        self.count = 0
        self.max_ns = 0
    def add(self, dur_ns:int):
        self.total_ns += dur_ns
        self.count += 1
        if dur_ns > self.max_ns:
            self.max_ns = dur_ns
    def snapshot(self):
        avg = self.total_ns / self.count if self.count else 0
        return avg, self.max_ns, self.count
    def reset(self):
        self.total_ns = 0; self.count = 0; self.max_ns = 0

class GaugeDiagnostics(QObject):
    updated = pyqtSignal()
    instance = None

    @staticmethod
    def get():
        if GaugeDiagnostics.instance is None:
            GaugeDiagnostics.instance = GaugeDiagnostics()
        return GaugeDiagnostics.instance

    def __init__(self):
        super().__init__()
        self._enabled = True
        self._stats_by_type = {}
        self._inputs = {}
        self._suppressed = {}
        self._coalesced = {}
        self._painted_values = {}
        self._last_snapshot = {}
        self._fps = 0
        self._frame_counter = 0
        self._timer = QTimer(self)
        # Prefer precise timer to reduce drift under GUI load
        try:
            self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        except Exception:
            pass
        self._timer.timeout.connect(self._roll)
        self._timer.start(1000)
    def enabled(self): return self._enabled
    def set_enabled(self, v:bool): self._enabled = v

    def record(self, gauge_type:str, duration_ns:int):
        if not self._enabled:
            return
        stats = self._stats_by_type.get(gauge_type)
        if stats is None:
            stats = PaintStats()
            self._stats_by_type[gauge_type] = stats
        stats.add(duration_ns)
        self._frame_counter += 1

    def record_input(self, gauge_type:str):
        self._inputs[gauge_type] = self._inputs.get(gauge_type, 0) + 1

    def record_suppressed(self, gauge_type:str):
        self._suppressed[gauge_type] = self._suppressed.get(gauge_type, 0) + 1

    def record_coalesced(self, gauge_type:str):
        self._coalesced[gauge_type] = self._coalesced.get(gauge_type, 0) + 1

    def record_painted_value(self, gauge_type:str, value:float):
        self._painted_values[gauge_type] = value

    def _roll(self):
        # Compute FPS as frames in last second
        self._fps = self._frame_counter
        self._frame_counter = 0
        snap = {}
        for k,v in self._stats_by_type.items():
            avg,maxv,count = v.snapshot()
            snap[k] = {
                'avg_ms': avg/1e6,
                'max_ms': maxv/1e6,
                'count': count,
                'inputs': self._inputs.get(k, 0),
                'suppressed': self._suppressed.get(k, 0),
                'coalesced': self._coalesced.get(k, 0),
                'last_value': self._painted_values.get(k)
            }
            v.reset()
        self._last_snapshot = snap
        # reset counters for next interval
        self._inputs = {}
        self._suppressed = {}
        self._coalesced = {}
        self.updated.emit()

    def snapshot(self):
        return {
            'fps': self._fps,
            'gauges': self._last_snapshot
        }

class DiagnosticsOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import Qt
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.setStyleSheet("background: transparent")
        self.font = QFont("DejaVu Sans Mono", 9)
        GaugeDiagnostics.get().updated.connect(self.update)

    def paintEvent(self, e):
        diag = GaugeDiagnostics.get().snapshot()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font)
        y = 12
        p.setPen(QColor(255,255,255))
        p.drawText(4,y,f"FPS: {diag['fps']}")
        y += 14
        for k,v in diag['gauges'].items():
            p.drawText(4,y,(f"{k}: avg {v['avg_ms']:.2f} ms max {v['max_ms']:.2f} ms paints {v['count']} "
                           f"in {v.get('inputs',0)} sup {v.get('suppressed',0)} coa {v.get('coalesced',0)}"))
            y += 14
        p.end()


class FixGwDiagnosticsPublisher(QObject):
    """Publishes GaugeDiagnostics snapshot into FIX database once per second."""
    def __init__(self, enabled: bool = True, key_prefix: str = "DIAG_", parent=None, log_enabled: bool = False):
        super().__init__(parent)
        self._enabled = enabled and (fix is not None)
        self._key_prefix = key_prefix
        self._log_enabled = bool(log_enabled)
        self._logger = logging.getLogger(__name__)
        if self._enabled or self._log_enabled:
            GaugeDiagnostics.get().updated.connect(self._publish)

    def _sanitize(self, s: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "_", s).upper()

    def _item(self, name: str):
        try:
            return fix.db.get_item(name)
        except Exception:
            return None

    def _set(self, key: str, value):
        item = self._item(key)
        if item is None:
            return
        try:
            item.value = value
            item.output_value()
        except Exception:
            pass

    def _publish(self):
        if not (self._enabled or self._log_enabled):
            return
        snap = GaugeDiagnostics.get().snapshot()
        prefix = self._key_prefix
        # Global FPS
        if self._log_enabled:
            self._logger.warning("[DIAG PUBLISH] %sFPS=%.1f", prefix, float(snap.get('fps', 0)))
        if self._enabled:
            self._set(f"{prefix}FPS", float(snap.get('fps', 0)))
        # Per-gauge-type metrics
        for cls, stats in snap.get('gauges', {}).items():
            base = f"{prefix}{self._sanitize(cls)}_"
            if self._log_enabled:
                self._logger.warning(
                    "[DIAG PUBLISH] %sAVG_MS=%.3f MAX_MS=%.3f PAINTS=%d INPUTS=%d SUPPRESSED=%d COALESCED=%d",
                    base,
                    float(stats.get('avg_ms', 0)),
                    float(stats.get('max_ms', 0)),
                    int(stats.get('count', 0)),
                    int(stats.get('inputs', 0)),
                    int(stats.get('suppressed', 0)),
                    int(stats.get('coalesced', 0)),
                )
            if self._enabled:
                self._set(base + "AVG_MS", float(stats.get('avg_ms', 0)))
                self._set(base + "MAX_MS", float(stats.get('max_ms', 0)))
                self._set(base + "PAINTS", int(stats.get('count', 0)))
                self._set(base + "INPUTS", int(stats.get('inputs', 0)))
                self._set(base + "SUPPRESSED", int(stats.get('suppressed', 0)))
                self._set(base + "COALESCED", int(stats.get('coalesced', 0)))
            lv = stats.get('last_value', None)
            if lv is not None:
                if self._log_enabled:
                    self._logger.warning("[DIAG PUBLISH] %sLAST_VALUE=%.3f", base, float(lv))
                if self._enabled:
                    try:
                        self._set(base + "LAST_VALUE", float(lv))
                    except Exception:
                        pass


class OverlayDiagnosticsLogger(QObject):
    """Logs overlay snapshot once per second at DEBUG level when enabled."""
    def __init__(self, enabled: bool = False, parent=None):
        super().__init__(parent)
        self._enabled = bool(enabled)
        self._logger = logging.getLogger(__name__)
        if self._enabled:
            GaugeDiagnostics.get().updated.connect(self._log)

    def _log(self):
        snap = GaugeDiagnostics.get().snapshot()
        self._logger.warning("[DIAG OVERLAY] FPS=%.1f", float(snap.get('fps', 0)))
        for cls, stats in snap.get('gauges', {}).items():
            self._logger.warning(
                "[DIAG OVERLAY] %s avg=%.3fms max=%.3fms paints=%d in=%d sup=%d coa=%d last=%s",
                cls,
                float(stats.get('avg_ms', 0)),
                float(stats.get('max_ms', 0)),
                int(stats.get('count', 0)),
                int(stats.get('inputs', 0)),
                int(stats.get('suppressed', 0)),
                int(stats.get('coalesced', 0)),
                ("%.3f" % float(stats.get('last_value'))) if stats.get('last_value') is not None else "-",
            )
