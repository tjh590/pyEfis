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

    New behavior (truncated bar fill): only the portion of the bar from the
    bottom up to the current value is filled, using a color determined by the
    zone thresholds. The area above the current value remains background.

    Zones (see `_current_zone`):
      - low_alarm / high_alarm: filled region (value height) = `alarmColor` (red)
      - low_warn: filled region = `warnColor` (yellow)
      - safe: filled region = `safeColor` (green)
      - high_warn: base of filled region up to `highWarn` = `safeColor`, and
        the segment from `highWarn` to current value = `warnColor`.

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

        # zone determination & geometry
        zone = self._current_zone()
        p = QPainter(self)
        try:
            bar_left = int(getattr(self, 'barLeft', 0))
            bar_top = int(getattr(self, 'barTop', 0))
            bar_width = int(getattr(self, 'barWidth', self.width()))
            bar_height = int(getattr(self, 'barHeight', self.height()))
            bar_bottom = bar_top + bar_height

            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setPen(Qt.PenStyle.NoPen)

            # Clear bar area background
            p.fillRect(QRect(bar_left, bar_top, bar_width, bar_height), self.bgColor)

            # Compute filled height based on current value
            try:
                value_height = int(round(self.interpolate(self.value, bar_height)))
            except Exception:
                value_height = 0
            if value_height < 0:
                value_height = 0
            if value_height > bar_height:
                value_height = bar_height

            if value_height > 0:
                if zone in ('low_alarm', 'high_alarm'):
                    # Entire filled region alarm color
                    p.fillRect(QRect(bar_left, bar_bottom - value_height, bar_width, value_height), self.alarmColor)
                elif zone == 'low_warn':
                    p.fillRect(QRect(bar_left, bar_bottom - value_height, bar_width, value_height), self.warnColor)
                elif zone == 'safe':
                    p.fillRect(QRect(bar_left, bar_bottom - value_height, bar_width, value_height), self.safeColor)
                elif zone == 'high_warn':
                    # Base safe segment up to highWarn, then warn segment for remainder
                    if self.highWarn is not None:
                        try:
                            hw_height = int(round(self.interpolate(self.highWarn, bar_height)))
                        except Exception:
                            hw_height = value_height  # fallback
                        hw_height = max(0, min(hw_height, value_height))
                        # Safe portion
                        if hw_height > 0:
                            p.fillRect(QRect(bar_left, bar_bottom - hw_height, bar_width, hw_height), self.safeColor)
                        # Warn portion
                        warn_height = value_height - hw_height
                        if warn_height > 0:
                            p.fillRect(QRect(bar_left, bar_bottom - value_height, bar_width, warn_height), self.warnColor)
                    else:
                        # No highWarn threshold defined; treat entire region as warn
                        p.fillRect(QRect(bar_left, bar_bottom - value_height, bar_width, value_height), self.warnColor)

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
