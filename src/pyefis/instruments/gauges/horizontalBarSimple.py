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

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

from .horizontalBarImproved import HorizontalBarImproved as HorizontalBarBase


class HorizontalBarSimple(HorizontalBarBase):
    """
    Simplified horizontal bar that changes color based on value.
    
    No color bands, no segments - just a clean filled bar that changes
    color (green/yellow/red) based on the current value and thresholds.
    
    This eliminates ALL alignment issues and gives a clean, modern look.
    """
    
    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super().__init__(parent, min_size, font_family)
        # Force segments to 0 to prevent any segment drawing
        self._segments_locked = True
        self.segments = 0
        # Simple variant supports peak indicator
        self.supportsPeak = True
    
    def __setattr__(self, name, value):
        # Prevent segments from being changed after initialization
        if name == 'segments' and hasattr(self, '_segments_locked'):
            return  # Ignore any attempts to set segments
        super().__setattr__(name, value)
    
    def _current_zone(self):
        """Return one of: 'low_alarm', 'low_warn', 'safe', 'high_warn', 'high_alarm'.
        Thresholds can be None and are treated as absent boundaries.
        """
        v = self._value
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
        # Check highlight status
        if self.highlight_key:
            if self._highlightValue == self._rawValue:
                self.highlight = True
            else:
                self.highlight = False

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        # Ensure geometry reflects late-applied flags
        try:
            self._recompute_geometry()
        except Exception:
            pass
        
        # Top row: name/dbkey + units combined (like HorizontalBarImproved)
        top_rect = QRectF(self.nameTextRect)
        fitted_font, (name_text, units_text, spacer, name_w) = self._get_top_layout()
        p.setFont(fitted_font)
        pen.setColor(self.textColor)
        p.setPen(pen)
        if name_text:
            opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if self.name_font_ghost_mask:
                alpha = self.textColor.alpha()
                self.textColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.drawText(top_rect, self.name_font_ghost_mask, opt_left)
                self.textColor.setAlpha(alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
            p.drawText(top_rect, name_text, opt_left)
            if units_text:
                units_rect = QRectF(top_rect.left() + name_w, top_rect.top(), max(0, top_rect.width() - name_w), top_rect.height())
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(units_rect, self.units_font_ghost_mask, opt_left)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(units_rect, units_text, opt_left)
        else:
            if units_text:
                opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(top_rect, self.units_font_ghost_mask, opt_left)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(top_rect, units_text, opt_left)
        
        # Draw value (inline, matching HorizontalBarImproved behavior)
        if self.show_value:
            if not self.value_on_bar_left:
                p.setFont(self.bigFont)
                opt_val = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
                if self.font_ghost_mask:
                    alpha = self.valueColor.alpha()
                    self.valueColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.valueColor)
                    p.setPen(pen)
                    p.drawText(self.valueTextRect, self.font_ghost_mask, opt_val)
                    self.valueColor.setAlpha(alpha)
                pen.setColor(self.valueColor)
                p.setPen(pen)
                p.drawText(self.valueTextRect, self.valueText, opt_val)
            else:
                # Value on the left label area next to bar
                label_text = self.valueText
                left_font = self._font_fit(self.bigFont, label_text or "", self.barValueRect)
                p.setFont(left_font)
                pen.setColor(self.valueColor)
                p.setPen(pen)
                opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                p.drawText(self.barValueRect, label_text, opt_left)

        # Units already handled in top row combined rendering above

        # ===== ZONE-BASED BAR DRAWING (value-dependent full-bar colors) =====
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(Qt.PenStyle.NoPen)

        bar_left, bar_top, bar_width, bar_height = self.get_bar_geometry()

        zone = self._current_zone()

        # Helper for threshold->pixel using improved base's geometry helpers
        def px(val):
            try:
                return int(self._calculateThresholdPixel(val)) if val is not None else None
            except Exception:
                return None

        lowAlarmPx = px(self.lowAlarm) if getattr(self, 'lowAlarm', None) is not None else None
        lowWarnPx = px(self.lowWarn) if getattr(self, 'lowWarn', None) is not None else None
        highWarnPx = px(self.highWarn) if getattr(self, 'highWarn', None) is not None else None
        highAlarmPx = px(self.highAlarm) if getattr(self, 'highAlarm', None) is not None else None

        # For horizontal bars, full bar color means entire width region; special case high-warn band overlay
        if zone in ('low_alarm', 'high_alarm'):
            p.fillRect(bar_left, bar_top, bar_width, bar_height, self.alarmColor)
        elif zone == 'low_warn':
            p.fillRect(bar_left, bar_top, bar_width, bar_height, self.warnColor)
        elif zone == 'safe':
            p.fillRect(bar_left, bar_top, bar_width, bar_height, self.safeColor)
        elif zone == 'high_warn':
            # Base is green
            p.fillRect(bar_left, bar_top, bar_width, bar_height, self.safeColor)
            # Overlay yellow in the high-warn band from highWarn..highAlarm (if any), else highWarn..end
            l_off = int(highWarnPx) if highWarnPx is not None else 0
            r_off = bar_width  # always extend to end; do not show red when in high-warn zone
            # Clamp to bar width and ensure l<=r
            l_off = max(0, min(bar_width, l_off))
            r_off = max(0, min(bar_width, r_off))
            if r_off < l_off:
                l_off, r_off = r_off, l_off
            band_w = r_off - l_off
            if band_w > 0:
                p.fillRect(bar_left + l_off, bar_top, band_w, bar_height, self.warnColor)
        
        # No highlight ball for horizontal bar

        # Peak value line
        if getattr(self, 'supportsPeak', True) and self.peakMode and self.peakValue is not None:
            pen.setColor(QColor(Qt.GlobalColor.white))
            brush = QBrush(self.peakColor)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(brush)
            bar_left, bar_top, bar_width, bar_height = self.get_bar_geometry()
            try:
                px = int(self.peakPixel())
                if px < 0 or px > bar_width:
                    rel = max(0.0, min(1.0, (self.peakValue - self.lowRange) / (self.highRange - self.lowRange))) if self.highRange != self.lowRange else 0.0
                    px = int(rel * bar_width)
            except Exception:
                px = int(self.interpolate(self.peakValue, bar_width)) if bar_width > 0 else 0
            px = max(0, min(bar_width, px))
            x = bar_left + px
            p.drawRect(qRound(x - 2), qRound(bar_top - 4), qRound(4), qRound(bar_height + 8))
