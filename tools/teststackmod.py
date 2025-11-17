#!/usr/bin/env python3
"""
Modified vertical bar gauge alignment test (teststackmod.py)
-----------------------------------------------------------------
This is a refinement of teststack.py intended to achieve pixel-perfect
alignment of the colored vertical bar zones by:
  * Disabling high-DPI scaling (optional toggle) for consistent logical pixels.
  * Using a single threshold mapping function with one rounding pass.
  * Building an ordered edge list and painting contiguous rectangles without
    cumulative rounding drift.
  * Using integer geometry (fillRect with int parameters) instead of QRectF.
  * Keeping shape antialiasing off while allowing text antialiasing.
  * Optional diagnostic: verify tessellation of zones (no gaps/overlaps).

You can adjust WINDOW_* constants or BAR_* parameters similarly to the original.
"""

import os
import sys
from typing import List, Optional
from dataclasses import dataclass
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QImage
from PyQt6.QtCore import Qt, QRect

# ===== ADJUSTABLE CONSTANTS =====
WINDOW_WIDTH = 3840
WINDOW_HEIGHT = 2160
BAR_COUNT = 6
BAR_WIDTH = 20
BAR_SPACING = 20
BAR_START_X = 50
BAR_START_Y = 100
WIDGET_HEIGHT = 160  # Uniform widget height for consistency
SHOW_NAME = True
SHOW_VALUE = True
SHOW_UNITS = True
TEXT_GAP = 3
SMALL_FONT_PERCENT = 0.08
BIG_FONT_PERCENT = 0.10

LOW_RANGE = 0
HIGH_RANGE = 300
LOW_ALARM = 50
LOW_WARN = 85
HIGH_WARN = 204
HIGH_ALARM = 232
CURRENT_VALUE = 180

SAFE_COLOR = QColor("#00FF00")
WARN_COLOR = QColor("#FFFF00")
ALARM_COLOR = QColor("#FF0000")
BG_COLOR = QColor(40, 40, 40)
FONT_FAMILY = "DejaVu Sans Condensed"
TITLE_FONT_SIZE = 16
LABEL_FONT_SIZE = 12

# Disable high DPI scaling for pixel exactness (optional)
# High DPI scaling control
# PyQt6 removed legacy Qt.AA_EnableHighDpiScaling / Qt.AA_UseHighDpiPixmaps constants.
# To force pixel alignment you can optionally disable scaling by setting env vars
# BEFORE constructing QApplication. Leave FORCE_NO_HIGH_DPI False unless you need
# to compare behavior.
FORCE_NO_HIGH_DPI = False  # Set True to force scale factor 1 via env vars below.
if FORCE_NO_HIGH_DPI:
    import os
    os.environ.setdefault("QT_SCALE_FACTOR", "1")          # Force logical=physical
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0") # Disable automatic scaling


def map_value_to_pixel(value: Optional[float], bar_top: int, bar_bottom: int) -> Optional[int]:
    """Map a data value to a pixel Y coordinate using a single rounding pass.
    Returns None if value outside range or invalid.
    Top is smaller y, bottom is larger y.
    """
    if value is None:
        return None
    if HIGH_RANGE == LOW_RANGE:
        return None
    # Clamp
    norm = (value - LOW_RANGE) / (HIGH_RANGE - LOW_RANGE)
    if norm < 0.0:
        norm = 0.0
    elif norm > 1.0:
        norm = 1.0
    bar_height = bar_bottom - bar_top
    # Pixel from top: invert because higher value should appear toward bottom
    pixel_from_top = (1.0 - norm) * bar_height
    return bar_top + int(round(pixel_from_top))


def compute_bar_geometry(widget_height: int):
    """Compute bar top/bottom using font percent logic (simplified)."""
    small_px = int(round(widget_height * SMALL_FONT_PERCENT)) if SHOW_NAME or SHOW_UNITS else 0
    big_px = int(round(widget_height * BIG_FONT_PERCENT)) if SHOW_VALUE else 0

    # Top offset after name
    bar_top = small_px + (TEXT_GAP if SHOW_NAME else 0)
    # Bottom offset before value + units
    bar_bottom = widget_height - big_px - (TEXT_GAP if SHOW_VALUE else 0)
    if SHOW_UNITS:
        bar_bottom -= (small_px + TEXT_GAP)
    return bar_top, bar_bottom, small_px, big_px


def ordered_edges(bar_top: int, bar_bottom: int) -> List[int]:
    """Build sorted unique edge list for zone boundaries."""
    edges = [bar_top, bar_bottom]
    for v in [HIGH_ALARM, HIGH_WARN, LOW_WARN, LOW_ALARM]:
        pix = map_value_to_pixel(v, bar_top, bar_bottom)
        if pix is not None:
            edges.append(pix)
    # Ensure within bounds and uniqueness
    edges = sorted(set(e for e in edges if bar_top <= e <= bar_bottom))
    return edges


def classify_segment(start: int, end: int, bar_top: int, bar_bottom: int) -> QColor:
    """Assign a color to the segment between start and end.

    Logical order top->bottom:
      [bar_top, HIGH_ALARM) -> ALARM (if high alarm defined)
      [HIGH_ALARM, HIGH_WARN) -> WARN
      [HIGH_WARN, LOW_WARN] -> SAFE
      [LOW_WARN, LOW_ALARM) -> WARN
      [LOW_ALARM, bar_bottom] -> ALARM
    If thresholds absent, defaults to SAFE.
    """
    # Fetch threshold pixels once
    ha = map_value_to_pixel(HIGH_ALARM, bar_top, bar_bottom)
    hw = map_value_to_pixel(HIGH_WARN, bar_top, bar_bottom)
    lw = map_value_to_pixel(LOW_WARN, bar_top, bar_bottom)
    la = map_value_to_pixel(LOW_ALARM, bar_top, bar_bottom)

    # Segment lies entirely in which zone?
    def in_range(a, b):
        return a is not None and b is not None

    # High alarm zone
    if ha is not None and start >= bar_top and end <= ha:
        return ALARM_COLOR
    # High warn zone
    if in_range(ha, hw) and start >= ha and end <= hw:
        return WARN_COLOR
    # Safe zone (between high warn and low warn)
    if in_range(hw, lw) and start >= hw and end <= lw:
        return SAFE_COLOR
    # Low warn zone
    if in_range(lw, la) and start >= lw and end <= la:
        return WARN_COLOR
    # Low alarm zone
    if la is not None and start >= la and end <= bar_bottom:
        return ALARM_COLOR

    # Fallback
    return SAFE_COLOR


@dataclass
class ExportOptions:
    png_path: Optional[str] = None
    overlay_lines: bool = False
    headless: bool = False
    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT


class VerticalBarMod(QWidget):
    def __init__(self, opts: ExportOptions):
        super().__init__()
        self.opts = opts
        self.setWindowTitle("Vertical Bar Alignment Test (Modified)")
        self.setFixedSize(opts.width, opts.height)
        self.setStyleSheet(f"background-color: rgb({BG_COLOR.red()}, {BG_COLOR.green()}, {BG_COLOR.blue()});")

    def paintEvent(self, event):
        p = QPainter(self)
        # Shape antialiasing off, enable text antialiasing only
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Title
        pen = QPen(QColor(255, 255, 255))
        p.setPen(pen)
        title_font = QFont(FONT_FAMILY, TITLE_FONT_SIZE, QFont.Weight.Bold)
        p.setFont(title_font)
        p.drawText(20, 40, "Vertical Bar Alignment Test (Modified)")
        info_font = QFont(FONT_FAMILY, LABEL_FONT_SIZE)
        p.setFont(info_font)
        p.drawText(20, 60, f"Value={CURRENT_VALUE} | Warn={HIGH_WARN} | Alarm={HIGH_ALARM}")

        # Draw bars
        for i in range(BAR_COUNT):
            bar_left = BAR_START_X + i * (BAR_WIDTH + BAR_SPACING)
            bar_top_rel, bar_bottom_rel, small_px, big_px = compute_bar_geometry(WIDGET_HEIGHT)
            # Absolute coords
            bar_top = BAR_START_Y + bar_top_rel
            bar_bottom = BAR_START_Y + bar_bottom_rel
            edges = ordered_edges(bar_top, bar_bottom)
            # Paint contiguous segments
            for a, b in zip(edges, edges[1:]):
                height = b - a
                if height <= 0:
                    continue
                color = classify_segment(a, b, bar_top, bar_bottom)
                p.fillRect(int(bar_left), int(a), int(BAR_WIDTH), int(height), color)
            # Label below
            pen.setColor(QColor(255, 255, 255))
            p.setPen(pen)
            p.setFont(info_font)
            label_y = bar_bottom + 10
            p.drawText(bar_left - 10, label_y + 20, f"BAR{i+1}")

        if self.opts.overlay_lines:
            self._verify_alignment(p)

        # If headless PNG export requested, render to image and save
        if self.opts.png_path and self.opts.headless:
            self._export_png()

    def _export_png(self):
        # Render the widget to a QImage and save
        img = QImage(self.width(), self.height(), QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        painter = QPainter(img)
        # Fill background
        painter.fillRect(QRect(0, 0, self.width(), self.height()), BG_COLOR)
        # Repaint content (duplicating logic from paintEvent)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        pen = QPen(QColor(255, 255, 255))
        painter.setPen(pen)
        title_font = QFont(FONT_FAMILY, TITLE_FONT_SIZE, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(20, 40, "Vertical Bar Alignment Test (Modified)")
        info_font = QFont(FONT_FAMILY, LABEL_FONT_SIZE)
        painter.setFont(info_font)
        painter.drawText(20, 60, f"Value={CURRENT_VALUE} | Warn={HIGH_WARN} | Alarm={HIGH_ALARM}")
        for i in range(BAR_COUNT):
            bar_left = BAR_START_X + i * (BAR_WIDTH + BAR_SPACING)
            bar_top_rel, bar_bottom_rel, small_px, big_px = compute_bar_geometry(WIDGET_HEIGHT)
            bar_top = BAR_START_Y + bar_top_rel
            bar_bottom = BAR_START_Y + bar_bottom_rel
            edges = ordered_edges(bar_top, bar_bottom)
            for a, b in zip(edges, edges[1:]):
                height = b - a
                if height <= 0:
                    continue
                color = classify_segment(a, b, bar_top, bar_bottom)
                painter.fillRect(int(bar_left), int(a), int(BAR_WIDTH), int(height), color)
            pen.setColor(QColor(255, 255, 255))
            painter.setPen(pen)
            painter.setFont(info_font)
            label_y = bar_bottom + 10
            painter.drawText(bar_left - 10, label_y + 20, f"BAR{i+1}")
        if self.opts.overlay_lines:
            self._verify_alignment(painter)
        painter.end()
        ok = img.save(self.opts.png_path)
        print(f"PNG export => {self.opts.png_path} (ok={ok})")

    def _verify_alignment(self, painter: QPainter):  # Debug helper
        # Draw thin horizontal lines across all bars at each edge to visually confirm alignment.
        pen = QPen(QColor(120, 120, 120))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        bar_top_rel, bar_bottom_rel, _, _ = compute_bar_geometry(WIDGET_HEIGHT)
        bar_top = BAR_START_Y + bar_top_rel
        bar_bottom = BAR_START_Y + bar_bottom_rel
        edges = ordered_edges(bar_top, bar_bottom)
        for e in edges:
            painter.drawLine(BAR_START_X - 5, e, BAR_START_X + BAR_COUNT * (BAR_WIDTH + BAR_SPACING), e)


def parse_args(argv) -> ExportOptions:
    import argparse
    parser = argparse.ArgumentParser(description="Vertical Bar Alignment Test (Modified) with PNG export")
    parser.add_argument("--png", dest="png_path", help="Path to export PNG (implies --headless)")
    parser.add_argument("--headless", action="store_true", help="Run without showing window (for PNG export)")
    parser.add_argument("--overlay-lines", action="store_true", help="Draw horizontal alignment guide lines")
    parser.add_argument("--width", type=int, default=WINDOW_WIDTH, help="Window/image width")
    parser.add_argument("--height", type=int, default=WINDOW_HEIGHT, help="Window/image height")
    args = parser.parse_args(argv)
    headless = args.headless or bool(args.png_path)
    return ExportOptions(png_path=args.png_path, overlay_lines=args.overlay_lines, headless=headless, width=args.width, height=args.height)


def main():
    opts = parse_args(sys.argv[1:])
    print("=" * 60)
    print("Modified Vertical Bar Alignment Test")
    print("=" * 60)
    print(f"Window: {opts.width}x{opts.height}")
    print(f"Bars: {BAR_COUNT} @ width {BAR_WIDTH}px")
    print(f"Range: {LOW_RANGE}..{HIGH_RANGE}")
    print(f"Thresholds: LOW_ALARM={LOW_ALARM} LOW_WARN={LOW_WARN} HIGH_WARN={HIGH_WARN} HIGH_ALARM={HIGH_ALARM}")
    print("Using single-pass rounding and ordered segments for pixel alignment.")
    if opts.png_path:
        print(f"PNG output requested: {opts.png_path}")
    app = QApplication(sys.argv)
    w = VerticalBarMod(opts)
    if not opts.headless:
        w.show()
        sys.exit(app.exec())
    # Headless path: trigger paint to export then quit
    w.show()  # Needed for proper sizing
    app.processEvents()
    # Manually invoke paintEvent via update/processing
    w.repaint()
    app.processEvents()
    # If still no export (guard), force one
    if opts.png_path and not os.path.exists(opts.png_path):
        w._export_png()
    print("Headless export complete.")
    app.quit()
    return 0


if __name__ == "__main__":
    main()
