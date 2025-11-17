#  Copyright (c) 2013 Phil Birkelbach
#  Copyright (c) 2025 Simplified single-color version
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

from PyQt6.QtGui import QPainter, QColor, QPaintEvent, QPen, QTextOption
from PyQt6.QtCore import QRect, QPointF, Qt
from PyQt6.QtWidgets import QWidget

from .verticalBarImproved import VerticalBarImproved as VerticalBarBase


class VerticalBarSimple(VerticalBarBase):
    """Minimal simplified vertical bar.

    Full-bar color based on current value zone:
      low_alarm / high_alarm -> alarmColor (red)
      low_warn -> warnColor (yellow)
      safe -> safeColor (green)
      high_warn -> safe base + warn overlay band between highWarn..highAlarm (or proportional top band if no highAlarm)
    """

    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super().__init__(parent, min_size, font_family)
        self.segments = 0  # force no segments

    def _current_zone(self):
        v = getattr(self, '_value', 0)
        if self.highAlarm is not None and v >= self.highAlarm:
            return 'high_alarm'
        if self.lowAlarm is not None and v <= self.lowAlarm:
            return 'low_alarm'
        if self.highWarn is not None and v >= self.highWarn:
            return 'high_warn'
        if self.lowWarn is not None and v <= self.lowWarn:
            return 'low_warn'
        return 'safe'

    def paintEvent(self, event):
        # Update highlight state (optional)
        try:
            if getattr(self, 'highlight_key', False):
                self.highlight = (self._highlightValue == self._rawValue)
        except Exception:
            pass

        # zone determination
        zone = self._current_zone()
        p = QPainter(self)
        try:
            # Background fill according to zone
            # Compute bar geometry from base class so we only paint inside the bar area
            bar_left = int(getattr(self, 'barLeft', 0))
            bar_top = int(getattr(self, 'barTop', 0))
            bar_width = int(getattr(self, 'barWidth', self.width()))
            bar_height = int(getattr(self, 'barHeight', self.height()))

            # No outline for fills to avoid border artifacts
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setPen(Qt.PenStyle.NoPen)

            if zone in ('low_alarm', 'high_alarm'):
                base_color = self.alarmColor
            elif zone == 'low_warn':
                base_color = self.warnColor
            else:
                base_color = self.safeColor
            p.fillRect(QRect(bar_left, bar_top, bar_width, bar_height), base_color)

            # ----- Text and value rendering aligned with Improved -----
            pen = QPen()
            pen.setWidth(1)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            # Name
            opt = QTextOption(Qt.AlignmentFlag.AlignCenter)
            if getattr(self, 'show_name', True):
                if getattr(self, 'name_font_ghost_mask', None):
                    opt = QTextOption(Qt.AlignmentFlag.AlignLeft)
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.setFont(self.smallFont)
                    p.drawText(self.nameTextRect, self.name_font_ghost_mask, opt)
                    self.textColor.setAlpha(alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.setFont(self.smallFont)
                p.drawText(self.nameTextRect, self.name, opt)

            # Value
            if getattr(self, 'show_value', True):
                if getattr(self, 'peakMode', False):
                    dv = self.value - self.peakValue
                    if dv <= -10:
                        pen.setColor(self.peakColor)
                        p.setFont(self.bigFont)
                        p.setPen(pen)
                        p.drawText(self.valueTextRect, str(round(dv)), QTextOption(Qt.AlignmentFlag.AlignCenter))
                    else:
                        self.drawValue(p, pen)
                else:
                    self.drawValue(p, pen)

            # Units
            pen.setColor(self.textColor)
            p.setPen(pen)
            if getattr(self, 'show_units', True):
                if getattr(self, 'units_font_mask', None):
                    opt = QTextOption(Qt.AlignmentFlag.AlignRight)
                    p.setFont(self.unitsFont)
                    if getattr(self, 'units_font_ghost_mask', None):
                        alpha = self.textColor.alpha()
                        self.textColor.setAlpha(self.font_ghost_alpha)
                        pen.setColor(self.textColor)
                        p.setPen(pen)
                        p.drawText(self.unitsTextRect, self.units_font_ghost_mask, opt)
                        self.textColor.setAlpha(alpha)
                        pen.setColor(self.textColor)
                        p.setPen(pen)
                    p.drawText(self.unitsTextRect, self.units, opt)
                else:
                    p.setFont(self.smallFont)
                    p.drawText(self.unitsTextRect, self.units, QTextOption(Qt.AlignmentFlag.AlignCenter))

            if zone == 'high_warn':
                # Overlay from the pixel corresponding to highWarn up to the top (ensures visible warning in samples)
                if self.highRange != self.lowRange and self.highWarn is not None:
                    # Map highWarn to pixel from top using improved threshold calculation
                    hw_pix = self._calculateThresholdPixel(self.highWarn)
                    if hw_pix is not None:
                        # hw_pix is absolute y from top; clamp inside bar and fill from bar_top to hw_pix
                        y_top = max(bar_top, int(hw_pix))
                        y_bottom = bar_top
                        if y_top > y_bottom:
                            p.fillRect(QRect(bar_left, y_bottom, bar_width, y_top - y_bottom), self.warnColor)

            # (Value text already rendered above for consistency)

            # Optional: highlight ball
            try:
                if getattr(self, 'highlight', False):
                    # Derive bar geometry from base attributes when available
                    bar_left = int(getattr(self, 'barLeft', bar_left))
                    bar_width = int(getattr(self, 'barWidth', bar_width))
                    bar_bottom = int(getattr(self, 'barBottom', bar_top + bar_height))
                    radius = max(1, int(round(bar_width * 0.40)))
                    cx = bar_left + (bar_width / 2.0)
                    cy = bar_bottom - (bar_width / 2.0)
                    p.setPen(QColor(Qt.GlobalColor.black))
                    p.setBrush(self.highlightColor)
                    p.drawEllipse(QPointF(cx, cy), radius, radius)
            except Exception:
                pass

            # Optional: peak value line
            try:
                if getattr(self, 'peakMode', False) and getattr(self, 'peakValue', None) is not None:
                    # Compute y position for peak value
                    bar_top = int(getattr(self, 'barTop', bar_top))
                    bar_height = int(getattr(self, 'barHeight', bar_height))
                    bar_bottom = bar_top + bar_height
                    if getattr(self, 'normalizeMode', False) and getattr(self, 'normalize_range', 0) > 0:
                        nval = self.peakValue - self.normalizeReference
                        start = bar_top + bar_height / 2
                        y = start - (nval * bar_height / self.normalize_range)
                    else:
                        # Fallback to interpolate helper from base if available
                        try:
                            y = bar_top + (bar_height - self.interpolate(self.peakValue, bar_height))
                        except Exception:
                            y = bar_top
                    # Clamp and draw small horizontal bar across the gauge bar area
                    y = max(bar_top, min(bar_bottom, int(y)))
                    bar_left = int(getattr(self, 'barLeft', bar_left))
                    bar_width = int(getattr(self, 'barWidth', bar_width))
                    p.setPen(QColor(Qt.GlobalColor.white))
                    p.setBrush(self.peakColor)
                    p.drawRect(bar_left, y - 2, bar_width, 4)
            except Exception:
                pass
        finally:
            p.end()
