# Peak Indicators

This document describes the unified Peak Indicator system for gauge widgets.

## Overview
Peak Mode tracks the maximum observed value while enabled and renders a marker (and optional delta text) so users can compare current readings against recent peaks (e.g., CHT, EGT, oil pressure). The implementation has been centralized in `AbstractGauge` to provide consistent behavior across vertical and horizontal bars.

## Core Attributes (All Gauges)
- `peakMode` (bool): Enables peak tracking. When true, `peakValue` records the highest value seen since activation or last reset.
- `peakValue` (float): Current stored peak. Updated only while `peakMode` is active.
- `peak_delta_threshold` (float): Minimum negative difference `(value - peakValue)` required before delta text replaces the normal value display (vertical bars). Default: `10.0`.
- `peak_indicator_thickness` (int): Thickness in pixels of the rendered peak marker rectangle. Default: `4`.
- `peak_indicator_extent` (int): Overshoot beyond bar region for horizontal indicators (visual emphasis). Default: `4`.
- `peakColor` (QColor): Color used for peak marker and delta text. Defaults to magenta unless overridden in a subclass or YAML.
- `supportsPeak` (bool): Indicates whether a given gauge class draws a peak marker. Base `HorizontalBar` sets this to `False`; improved/simple variants set `True`.

## Behavior Summary
1. Activation: Setting `peakMode = True` seeds `peakValue` with the current value.
2. Advancement: On each value update (while enabled), if new value > `peakValue`, it becomes the new peak and schedules a repaint.
3. Delta Display (vertical bars): If `value - peakValue <= -peak_delta_threshold`, delta (negative number) is drawn in `peakColor`; otherwise normal value text is drawn.
4. Indicator Rendering:
   - Vertical Bars: A horizontal rectangle across the bar at the peak position.
   - Horizontal Bars: A vertical rectangle spanning the bar height (+/- extent) at the peak x position.
5. Reset: Calling `resetPeak()` sets `peakValue = current value` and repaints immediately.

## YAML Configuration
You can set peak-related attributes per gauge in your instrument YAML or aggregated configuration binding (where gauge instances are constructed). Example snippet:

```yaml
instruments:
  - name: CHT1
    type: VerticalBarImproved
    dbkey: CHT1
    peakMode: true               # Start in peak mode
    peakColor: "#FF00FF"         # Custom magenta
    peak_delta_threshold: 15.0   # Show delta if drop >= 15
    peak_indicator_thickness: 6  # Thicker peak marker
  - name: OILP
    type: HorizontalBarImproved
    dbkey: OILP1
    peakMode: true
    peakColor: "#00FFFF"         # Cyan marker
    supportsPeak: true           # (Redundant here; shown for completeness)
```

### Accepted Keys
The following keys may be bound directly onto a gauge instance via the existing attribute binding mechanism:
- `peakMode`
- `peakColor` (hex string or predefined name that PyQt can parse)
- `peak_delta_threshold`
- `peak_indicator_thickness`
- `peak_indicator_extent`
- `supportsPeak`

Any omitted key falls back to its default defined in `AbstractGauge` or subclass.

## Programmatic Control
Actions (e.g., from keybindings or encoder interaction) can toggle or reset peak:
- Toggle Peak: `gauge.peakMode = not gauge.peakMode`
- Reset Peak: `gauge.resetPeak()`

Combined modes (e.g., "lean") may enable normalization and peak simultaneously.

## Diagnostics & Future Extensions
Potential future enhancements:
- Peak decay mode: Gradually lower `peakValue` toward current value when difference exceeds a margin.
- Multi-peak history: Store recent peaks in a ring buffer.
- Overlay metrics: Record peak updates and paints for performance dashboards.

## Testing Notes
Automated tests (`tests/instruments/gauges/test_peak_mode.py` and `test_peak_highlight.py`) validate:
- Peak advancement only when enabled.
- Delta text threshold logic.
- Marker drawing depending on `supportsPeak`.

## Migration Notes
Legacy hard-coded -10 delta checks have been replaced with configurable `peak_delta_threshold`. Vertical and horizontal drawing have been standardized around `peakPixel()` helper.

## Troubleshooting
| Symptom | Possible Cause | Resolution |
|---------|----------------|------------|
| Peak marker not visible | `supportsPeak=False` on gauge | Set `supportsPeak: true` in YAML or subclass init. |
| Delta text never appears | Threshold too large or peak not higher than historical | Lower `peak_delta_threshold` or confirm peakMode enabled early. |
| Delta text always appears | Threshold too small; frequent peak resets | Increase `peak_delta_threshold` or avoid unnecessary resets. |

## Example Minimal YAML Entry
```yaml
- name: CHT2
  type: VerticalBarSimple
  dbkey: CHT2
  peakMode: true
  peak_delta_threshold: 12.5
  peak_indicator_thickness: 5
```

---
For additional layout details see `docs/improved_gauges.md` and the screen builder documentation.
