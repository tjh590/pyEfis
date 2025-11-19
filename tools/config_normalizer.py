#!/usr/bin/env python3

"""
Config Normalizer CLI

Build a normalized JSON snapshot of the pyEfis configuration:
- Loads preferences.yaml (+ .custom overrides)
- Resolves includes in default.yaml root and any screen YAMLs
- Expands ganged instruments to their child instrument nodes
- Merges preferences.styles and preferences.gauges into effective options
- Emits provenance for each node (file path, include chain, pref paths)

Usage:
  python3 tools/config_normalizer.py \
    --config config/default.yaml \
    --out tools/cfg_explorer/normalized_config.json

You can then open tools/cfg_explorer/index.html to browse the data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml


# ---------- Preferences merging ----------

def deep_merge(a: Any, b: Any) -> Any:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return b if b is not None else a
    out = dict(a)
    for k, v in b.items():
        if k in out:
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_preferences(base_dir: str) -> Dict[str, Any]:
    pref_path = os.path.join(base_dir, "preferences.yaml")
    with open(pref_path, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}
    cust_path = pref_path + ".custom"
    if os.path.exists(cust_path):
        with open(cust_path, "r", encoding="utf-8") as f:
            custom = yaml.safe_load(f) or {}
        return deep_merge(base, custom)
    return base


# ---------- Include resolution ----------

def resolve_include(base_config_dir: str, current_file_dir: str, logical_or_path: str, preferences: Dict[str, Any]) -> Tuple[str, str]:
    # 1) relative to current file
    cand = os.path.join(current_file_dir, logical_or_path)
    if os.path.exists(cand):
        return logical_or_path, os.path.normpath(cand)
    # 2) relative to base dir
    cand = os.path.join(base_config_dir, logical_or_path)
    if os.path.exists(cand):
        return logical_or_path, os.path.normpath(cand)
    # 3) preferences.includes mapping
    mapping = (preferences or {}).get("includes", {})
    mapped = mapping.get(logical_or_path)
    if mapped:
        cand = os.path.join(current_file_dir, mapped)
        if os.path.exists(cand):
            return logical_or_path, os.path.normpath(cand)
        cand = os.path.join(base_config_dir, mapped)
        if os.path.exists(cand):
            return logical_or_path, os.path.normpath(cand)
    raise FileNotFoundError(f"Cannot resolve include: {logical_or_path}")


# ---------- Normalization ----------

NodeId = int


@dataclass
class Node:
    id: NodeId
    type: str
    label: str
    file: str
    path: List[str] = field(default_factory=list)
    values: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)


class Normalizer:
    def __init__(self, base_dir: str, preferences: Dict[str, Any], defines: Optional[Dict[str, bool]] = None):
        self.base_dir = base_dir
        self.preferences = preferences or {}
        self.defines = defines or {}
        self.nodes: List[Node] = []
        self.edges: List[Dict[str, Any]] = []
        self._id = 1
        # includes_used maps resolved absolute include file path -> {logical, count, locations: [context strings]}
        self.includes_used: Dict[str, Dict[str, Any]] = {}

    def _next_id(self) -> NodeId:
        nid = self._id
        self._id += 1
        return nid

    # Preference helpers
    def _merge_styles(self, inst: Dict[str, Any]) -> Dict[str, Any]:
        """Merge preferences.styles based on BAR/ARC/TEXT families and preferences.gauges overrides."""
        opts = dict(inst.get('options', {}))
        pref_key = inst.get('preferences')
        styles = (self.preferences or {}).get('styles', {})
        style_switches = (self.preferences or {}).get('style', {})

        # Determine family from preference id (BARxxx → BAR)
        family = None
        if isinstance(pref_key, str):
            family = ''.join([c for c in pref_key if c.isalpha()]) or None
        # Apply global style switches for this family
        if family and family in styles:
            fam_styles = styles[family]
            for style_name, enabled in (style_switches or {}).items():
                if enabled and style_name in fam_styles and fam_styles[style_name] is not None:
                    opts |= fam_styles[style_name]
        # Apply gauge-specific overrides
        gspec = (self.preferences or {}).get('gauges', {})
        if isinstance(pref_key, str) and pref_key in gspec:
            # type override may live here
            g = gspec[pref_key]
            t = g.get('type')
            if t:
                inst['type'] = self._normalize_type_name(t)
            # merge remaining options
            inst['options'] = (inst.get('options', {}) | {k: v for k, v in g.items() if k != 'type'})
            opts |= {k: v for k, v in g.items() if k != 'type'}
        inst['options'] = opts
        return inst

    def _normalize_type_name(self, t: str) -> str:
        return t.strip()

    # Include traversal
    def walk_file(self, file_path: str, parent_path: List[str] | None = None, breadcrumb: List[str] | None = None) -> Dict[str, Any]:
        parent_path = parent_path or []
        breadcrumb = breadcrumb or []
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        cur_dir = os.path.dirname(file_path)
        # Resolve includes at mapping level and list level
        def resolve_in_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
            out = {}
            for k, v in (mapping or {}).items():
                if k == 'include':
                    files = v if isinstance(v, list) else [v]
                    inc_nodes = []
                    for inc in files:
                        logical, resolved = resolve_include(self.base_dir, cur_dir, inc, self.preferences)
                        rec = self.includes_used.setdefault(resolved, {'logical': logical, 'count': 0, 'locations': []})
                        rec['count'] += 1
                        # Record location context (current file and path chain)
                        loc = f"{os.path.relpath(file_path, self.base_dir)}:{'/'.join(parent_path + ['include'])}" if parent_path else os.path.relpath(file_path, self.base_dir)
                        rec['locations'].append(loc)
                        sub = self.walk_file(resolved, parent_path, breadcrumb + [f'include:{logical}'])
                        inc_nodes.append(sub)
                    out[k] = inc_nodes
                else:
                    out[k] = resolve(v)
            return out

        def resolve(value: Any) -> Any:
            if isinstance(value, dict):
                return resolve_in_mapping(value)
            if isinstance(value, list):
                items = []
                for i, e in enumerate(value):
                    if isinstance(e, dict) and 'include' in e:
                        logical, resolved = resolve_include(self.base_dir, cur_dir, e['include'], self.preferences)
                        rec = self.includes_used.setdefault(resolved, {'logical': logical, 'count': 0, 'locations': []})
                        rec['count'] += 1
                        loc = f"{os.path.relpath(file_path, self.base_dir)}:{'/'.join(parent_path + [str(i), 'include'])}" if parent_path else f"{os.path.relpath(file_path, self.base_dir)}:{str(i)}"
                        rec['locations'].append(loc)
                        sub = self.walk_file(resolved, parent_path, breadcrumb + [f'include:{logical}'])
                        items.append({'[include]': sub})
                    else:
                        items.append(resolve(e))
                return items
            return value

        return resolve_in_mapping(data)

    # Instruments expansion (screen-level)
    def expand_screen(self, screen_doc: Dict[str, Any], screen_file: str) -> Dict[str, Any]:
        layout = ((screen_doc or {}).get('layout') or {})
        instruments = (screen_doc or {}).get('instruments') or []
        flat_instruments: List[Dict[str, Any]] = []
        for inst in instruments:
            if not isinstance(inst, dict):
                continue
            # Expand include wrapper nodes generated by walk_file
            if 'type' in inst and 'include,' in str(inst.get('type')):
                # Included instruments already expanded by screenbuilder at runtime; here we just retain reference
                flat_instruments.append({'type': str(inst['type']), 'row': inst.get('row'), 'column': inst.get('column'), 'span': inst.get('span')})
                continue
            if 'type' in inst and 'ganged' in str(inst['type']):
                if 'gang_type' not in inst:
                    continue
                for g in inst.get('groups', []) or []:
                    for gi in g.get('instruments', []) or []:
                        child = {
                            'type': inst['type'].replace('ganged_', ''),
                            'group': g.get('name'),
                            'row': inst.get('row'),
                            'column': inst.get('column'),
                            'span': inst.get('span'),
                            'preferences': gi.get('preferences'),
                            'options': (g.get('common_options', {}) | gi.get('options', {})),
                        }
                        child = self._merge_styles(child)
                        flat_instruments.append(child)
                continue
            # Regular instrument
            inst = self._merge_styles(inst)
            flat_instruments.append(inst)
        return {
            'layout': layout,
            'instruments': flat_instruments,
            'file': screen_file,
        }

    def normalize(self, default_yaml: str) -> Dict[str, Any]:
        # Load root config
        root = self.walk_file(default_yaml)
        # Gather screens: keys under top-level likely refer to screen YAMLs included by default.yaml
        # For simplicity, look under 'screens' include if present; otherwise, accept any screen-like mapping with 'layout' + 'instruments'.
        normalized = {
            'meta': {
                'base_dir': self.base_dir,
                'default': os.path.relpath(default_yaml, self.base_dir),
            },
            'preferences': {
                'raw': self.preferences,  # merged explicit YAML (preferences.yaml + .custom)
                'implicit_defaults': {
                    'type_ratios': {
                        'vertical_bar': 0.35,
                        'horizontal_bar': 2.0,
                        'arc_gauge': 2.0,
                        'airspeed': 1.0,
                        'altimeter': 1.0,
                        'horizontal_situation_indicator': 1.0
                    }
                }
            },
            'includes': [],
            'buttons': [],
            'screens': [],
        }

        # Populate includes array with content for non-screen YAMLs
        for path, rec in sorted(self.includes_used.items()):
            rel = os.path.relpath(path, self.base_dir)
            is_screen = os.path.abspath(path).startswith(os.path.abspath(os.path.join(self.base_dir, 'screens')) + os.sep)
            entry = {
                'file': rel,
                'logical': rec.get('logical'),
                'used': rec.get('count', 0),
                'locations': sorted(rec.get('locations', [])),
                'is_screen': bool(is_screen),
            }
            if not is_screen:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        entry['content'] = yaml.safe_load(f) or {}
                except Exception:
                    entry['content'] = None
            normalized['includes'].append(entry)

        # Find candidate screen files from default.yaml's EMS/PFD/radio entries if present
        # Otherwise, allow user to pass a screen YAML directly with --screen
        # As a pragmatic approach: scan config/screens for YAML files and include those present in default.yaml mapping.
        screens_dir = os.path.join(self.base_dir, 'screens')
        def type_ratio(t: str) -> Optional[float]:
            t = (t or '').lower()
            # Derive ratio from instrument type families
            if 'vertical_bar' in t:
                return 0.35
            if 'horizontal_bar' in t:
                return 2.0
            if 'arc_gauge' in t:
                return 2.0
            if 'airspeed' in t:
                return 1.0
            if 'altimeter' in t:
                return 1.0
            if 'horizontal_situation_indicator' in t:
                return 1.0
            return None

        def bounding_box(width: float, height: float, x: float, y: float, ratio: float) -> Tuple[float,float,float,float]:
            # mirror of screenbuilder.get_bounding_box
            if width < height:
                r_height = width / ratio
                r_width = width
                if height < r_height:
                    r_height = height
                    r_width = height * ratio
            else:
                r_width = height * ratio
                r_height = height
                if width < r_width:
                    r_height = width / ratio
                    r_width = width
            if r_height == height:
                r_y = y
                r_x = x + ((width - r_width)/2)
            else:
                r_x = x
                r_y = y + ((height - r_height)/2)
            return (r_width, r_height, r_x, r_y)

        def grid_margins(layout: Dict[str,Any], W: float, H: float) -> Tuple[float,float,float,float]:
            # mirror of get_grid_margins (uses height for all percents)
            topm = leftm = rightm = bottomm = 0.0
            m = (layout or {}).get('margin', {}) or {}
            def pct(v):
                try:
                    return float(v)
                except Exception:
                    return 0.0
            if 'top' in m and 0 < pct(m['top']) < 100:
                topm = H * (pct(m['top'])/100.0)
            if 'bottom' in m and 0 < pct(m['bottom']) < 100:
                bottomm = H * (pct(m['bottom'])/100.0)
            if 'left' in m and 0 < pct(m['left']) < 100:
                leftm = H * (pct(m['left'])/100.0)
            if 'right' in m and 0 < pct(m['right']) < 100:
                rightm = H * (pct(m['right'])/100.0)
            return topm, leftm, rightm, bottomm

        def grid_coordinates(layout: Dict[str,Any], col: float, row: float, W: float, H: float) -> Tuple[float,float,float,float]:
            topm, leftm, rightm, bottomm = grid_margins(layout, W, H)
            cols = max(1, int((layout or {}).get('columns') or 1))
            rows = max(1, int((layout or {}).get('rows') or 1))
            grid_width = (W - leftm - rightm) / cols
            grid_height = (H - topm - bottomm) / rows
            grid_x = leftm + grid_width * (col or 0)
            grid_y = topm + grid_height * (row or 0)
            return grid_x, grid_y, grid_width, grid_height

        def compute_geometry(sbody: Dict[str,Any], screen_file: str, preview_w: int = 1200, preview_h: int = 800) -> Dict[str,Any]:
            layout = (sbody or {}).get('layout') or {}
            items_in = (sbody or {}).get('instruments') or []
            W, H = float(preview_w), float(preview_h)
            items_out: List[Dict[str,Any]] = []
            provenance_out: List[Dict[str,Any]] = []
            # Helpers: condition evaluation for 'disabled'
            def _has_defines() -> bool:
                return bool(self.defines)
            def _env_get(name: str) -> bool:
                return bool(self.defines.get(name, False))
            def _is_disabled(dv: Any) -> bool:
                if not _has_defines():
                    return False
                if isinstance(dv, bool):
                    return dv
                if isinstance(dv, (int, float)):
                    return bool(dv)
                if isinstance(dv, str):
                    s = dv.strip()
                    # support 'not VAR' or 'VAR'
                    if s.lower().startswith('not '):
                        var = s[4:].strip()
                        return not _env_get(var)
                    # allow bare var name; unknown vars => False
                    return _env_get(s)
                return False
            # Expand include items into child instruments with scaled rows/columns
            def load_include_instruments(cur_dir: str, inc: str) -> List[Dict[str,Any]]:
                try:
                    logical, resolved = resolve_include(self.base_dir, cur_dir, inc, self.preferences)
                except Exception:
                    return []
                try:
                    with open(resolved, 'r', encoding='utf-8') as f:
                        inc_doc = yaml.safe_load(f) or {}
                except Exception:
                    return []
                if isinstance(inc_doc, dict) and 'instruments' in inc_doc:
                    return inc_doc.get('instruments') or []
                if isinstance(inc_doc, dict) and len(inc_doc) > 0:
                    key = next(iter(inc_doc.keys()))
                    maybe = inc_doc.get(key) or {}
                    if isinstance(maybe, dict):
                        return maybe.get('instruments') or []
                return []

            def include_extents(cur_dir: str, inc: str, parent_rows: float, parent_cols: float) -> Tuple[float,float]:
                """Mirror calc_includes: compute max extents (row+span, col+span) inside include.
                parent_rows/cols are span rows/cols passed from caller (p_rows/p_cols)."""
                insts = load_include_instruments(cur_dir, inc)
                inst_rows = 0.0
                inst_cols = 0.0
                for inst in insts:
                    a_rows = parent_rows
                    a_cols = parent_cols
                    if 'span' in inst and isinstance(inst['span'], dict):
                        if 'rows' in inst['span']:
                            a_rows = inst['span']['rows']
                        if 'columns' in inst['span']:
                            a_cols = inst['span']['columns']
                        # accumulate extents
                        if a_rows + float(inst.get('row',0) or 0) > inst_rows:
                            inst_rows = a_rows + float(inst.get('row',0) or 0)
                        if a_cols + float(inst.get('column',0) or 0) > inst_cols:
                            inst_cols = a_cols + float(inst.get('column',0) or 0)
                    else:
                        t = str(inst.get('type',''))
                        if 'include,' in t:
                            # nested include resolution
                            pp_rows = inst_rows if inst_rows > 0 else parent_rows
                            pp_cols = inst_cols if inst_cols > 0 else parent_cols
                            sub = t.split(',',1)[1]
                            rows_sub, cols_sub = include_extents(cur_dir, sub, pp_rows, pp_cols)
                            if rows_sub + float(inst.get('row',0) or 0) > inst_rows:
                                inst_rows = rows_sub + float(inst.get('row',0) or 0)
                            if cols_sub + float(inst.get('column',0) or 0) > inst_cols:
                                inst_cols = cols_sub + float(inst.get('column',0) or 0)
                        else:
                            inst_rows = parent_rows
                            inst_cols = parent_cols
                if inst_rows == 0:
                    inst_rows = parent_rows
                if inst_cols == 0:
                    inst_cols = parent_cols
                return (inst_rows, inst_cols)

            def expand_includes(items: List[Dict[str,Any]], cur_dir: str, chain: Optional[List[str]] = None) -> List[Dict[str,Any]]:
                out: List[Dict[str,Any]] = []
                for inst in items:
                    if not isinstance(inst, dict):
                        continue
                    t = str(inst.get('type',''))
                    if 'include,' in t:
                        # If include wrapper itself is disabled based on defines, skip expansion entirely
                        if _is_disabled(inst.get('disabled')):
                            continue
                        inc = t.split(',', 1)[1]
                        new_chain = (chain or []) + [inc]
                        span = inst.get('span', {}) or {}
                        span_rows = float(span.get('rows', 0) or 0)
                        span_cols = float(span.get('columns', 0) or 0)
                        # Compute include extents using span_rows/span_cols as parent sizing
                        er, ec = include_extents(cur_dir, inc, span_rows, span_cols)
                        # Use extents if spans not provided
                        if span_rows == 0: span_rows = er
                        if span_cols == 0: span_cols = ec
                        row_p = (span_rows / er) if er else 1.0
                        col_p = (span_cols / ec) if ec else 1.0
                        base_row = float(inst.get('row', 0) or 0)
                        base_col = float(inst.get('column', 0) or 0)
                        children = load_include_instruments(cur_dir, inc)
                        for ci in children:
                            ci2 = json.loads(json.dumps(ci))
                            ci2['row'] = (float(ci.get('row', 0) or 0) * row_p) + base_row
                            ci2['column'] = (float(ci.get('column', 0) or 0) * col_p) + base_col
                            if 'span' in ci2 and isinstance(ci2['span'], dict):
                                ci2['span'] = dict(ci2['span'])
                                if 'rows' in ci2['span'] and ci2['span']['rows'] is not None:
                                    ci2['span']['rows'] = float(ci2['span']['rows']) * row_p
                                if 'columns' in ci2['span'] and ci2['span']['columns'] is not None:
                                    ci2['span']['columns'] = float(ci2['span']['columns']) * col_p
                            # Stash include chain provenance at child level
                            ci2['_include_chain'] = list(new_chain)
                            out.append(ci2)
                        # Recurse for nested includes within children
                        # Nested includes inside newly added children will be handled on next expansion pass
                    else:
                        out.append(inst)
                return out

            cur_dir = os.path.dirname(screen_file)
            items_in = expand_includes(items_in, cur_dir, [])
            def _label_for(inst_type: str, inst_obj: Dict[str,Any]) -> Optional[str]:
                try:
                    t = (inst_type or '').lower()
                    opts = (inst_obj or {}).get('options') or {}
                    if 'value_text' in t:
                        v = opts.get('dbkey')
                        return str(v) if v is not None else None
                    if 'static_text' in t:
                        v = opts.get('text')
                        return str(v) if v is not None else None
                    if 'numeric_display' in t:
                        v = opts.get('dbkey')
                        return str(v) if v is not None else None
                except Exception:
                    return None
                return None

            def _button_summary_from_options(opts: Dict[str,Any], cur_dir_local: str) -> Optional[str]:
                try:
                    if not isinstance(opts, dict):
                        return None
                    cfg = opts.get('config')
                    if not cfg:
                        return None
                    # Resolve candidate paths: absolute, relative to current screen dir, relative to base config dir
                    candidates = []
                    if os.path.isabs(str(cfg)):
                        candidates.append(str(cfg))
                    candidates.append(os.path.normpath(os.path.join(cur_dir_local, str(cfg))))
                    candidates.append(os.path.normpath(os.path.join(self.base_dir, str(cfg))))
                    path = next((p for p in candidates if os.path.exists(p)), None)
                    if not path:
                        return None
                    with open(path, 'r', encoding='utf-8') as f:
                        bdoc = yaml.safe_load(f) or {}
                    if not isinstance(bdoc, dict):
                        return None
                    stem = os.path.splitext(os.path.basename(path))[0]
                    label_base = bdoc.get('label') or bdoc.get('text') or stem
                    btype = bdoc.get('type')
                    conds = bdoc.get('conditions') or []
                    cond_count = len(conds)
                    # Extract up to 3 symbols across all conditions
                    import re
                    def _extract_syms(expr: Any) -> List[str]:
                        if not isinstance(expr, str):
                            return []
                        tokens = re.split(r"[^A-Za-z0-9_\.]+", expr)
                        syms: List[str] = []
                        for tkn in tokens:
                            if not tkn:
                                continue
                            tl = tkn.lower()
                            if tl in ('and','or','not','eq','ne','lt','gt','le','ge','true','false','clicked','previous_condition'):
                                continue
                            base = tkn.split('.',1)[0]
                            if base and base.isupper():
                                if base not in syms:
                                    syms.append(base)
                        return syms
                    symbols: List[str] = []
                    for c in conds:
                        for s in _extract_syms((c or {}).get('when')):
                            if s not in symbols:
                                symbols.append(s)
                    sym_part = ', '.join(symbols[:3])
                    parts = []
                    if btype:
                        parts.append(f"[{btype}]")
                    parts.append(str(label_base))
                    if cond_count:
                        parts.append(f"({cond_count})")
                    summary = ' '.join(parts)
                    if sym_part:
                        summary = f"{summary} — {sym_part}"
                    return summary
                except Exception:
                    return None
            # Iterate original instruments to handle ganged
            for inst in items_in:
                if not isinstance(inst, dict):
                    continue
                # Skip disabled instruments only when defines are provided
                if _is_disabled(inst.get('disabled')):
                    continue
                t = str(inst.get('type',''))
                row = float(inst.get('row', 0) or 0)
                col = float(inst.get('column', 0) or 0)
                span = inst.get('span', {}) or {}
                span_rows = float(span.get('rows', 0) or 0)
                span_cols = float(span.get('columns', 0) or 0)
                gx, gy, gw, gh = grid_coordinates(layout, col, row, W, H)
                if span_rows >= 0:
                    gh = gh * (span_rows or 1)
                if span_cols >= 0:
                    gw = gw * (span_cols or 1)
                x, y, width, height = gx, gy, gw, gh
                # Handle move/shrink/justify
                mv = inst.get('move') or {}
                if isinstance(mv, dict):
                    shrink = mv.get('shrink')
                    try:
                        if shrink is not None and 0 <= float(shrink) < 99:
                            r_width = width - (width * float(shrink)/100.0)
                            r_height = height - (height * float(shrink)/100.0)
                        else:
                            r_width, r_height = width, height
                    except Exception:
                        r_width, r_height = width, height
                    # justify
                    jlist = mv.get('justify') or []
                    if isinstance(jlist, str):
                        jlist = [jlist]
                    jh = jv = False
                    rx = x
                    ry = y
                    for j in jlist:
                        if j == 'left':
                            rx = x; jh = True
                        elif j == 'right':
                            rx = x + (width - r_width); jh = True
                        elif j == 'top':
                            ry = y; jv = True
                        elif j == 'bottom':
                            ry = y + (height - r_height); jv = True
                    if not jh:
                        rx = x + ((width - r_width)/2)
                    if not jv:
                        ry = y + ((height - r_height)/2)
                    x, y, width, height = rx, ry, r_width, r_height

                if 'include,' in t:
                    # Should have been expanded above
                    continue
                include_chain = inst.get('_include_chain') or []
                pref_key = inst.get('preferences') if isinstance(inst.get('preferences'), str) else None
                if 'ganged' in t:
                    gang_type = inst.get('gang_type','vertical')
                    groups = inst.get('groups') or []
                    inst_count = sum(len((g or {}).get('instruments') or []) for g in groups) or 1
                    if 'horizontal' in gang_type:
                        total_gaps = (len(groups) - 1) * (width * (2/100.0)) if len(groups) > 1 else 0
                        group_width = (width - total_gaps) / inst_count
                        group_height = height
                    else:
                        total_gaps = (len(groups) - 1) * (height * (6/100.0)) if len(groups) > 1 else 0
                        group_height = (height - total_gaps) / inst_count
                        group_width = width
                    gap_size = (total_gaps / (len(groups)-1)) if len(groups) > 1 else 0
                    group_x = x
                    group_y = y
                    for g in groups:
                        glist = (g or {}).get('instruments') or []
                        gap_pct = float((g or {}).get('gap', 0) or 0) / 100.0
                        if 'horizontal' in gang_type:
                            hgap = gap_pct * group_width
                            vgap = 0
                        else:
                            vgap = gap_pct * group_height
                            hgap = 0
                        # Compute child base rect
                        g_width = group_width   - ( hgap * (max(0, len(glist) - 1)))
                        g_height = group_height - ( vgap * (max(0, len(glist) - 1)))
                        base_child_type = t.replace('ganged_','')
                        r = type_ratio(base_child_type)
                        for idx, gi in enumerate(glist):
                            # Child-level disabled (rare) respected if present and defines provided
                            if _is_disabled(gi.get('disabled')):
                                continue
                            cw, ch, cx, cy = g_width, g_height, group_x, group_y
                            if r:
                                bw, bh, bx, by = bounding_box(cw, ch, cx, cy, r)
                                cw, ch, cx, cy = bw, bh, bx, by
                            # Preference override resolution
                            pref_child_key = gi.get('preferences') if isinstance(gi.get('preferences'), str) else None
                            concrete_type = base_child_type
                            if pref_child_key and isinstance(self.preferences.get('gauges'), dict):
                                gspec = self.preferences['gauges'].get(pref_child_key)
                                if isinstance(gspec, dict) and gspec.get('type'):
                                    concrete_type = str(gspec.get('type')).strip()
                            # Merge options (group common + child options) for labeling
                            merged_opts = {}
                            try:
                                if isinstance(g.get('common_options'), dict):
                                    merged_opts |= g.get('common_options')
                                if isinstance(gi.get('options'), dict):
                                    merged_opts |= gi.get('options')
                            except Exception:
                                pass
                            gi_for_label = dict(gi)
                            if merged_opts:
                                gi_for_label = dict(gi_for_label)
                                gi_for_label['options'] = merged_opts
                            display_label = _label_for(concrete_type, gi_for_label)
                            if not display_label and 'button' in str(concrete_type).lower():
                                display_label = _button_summary_from_options(merged_opts or {}, cur_dir)
                            items_out.append({
                                'type': concrete_type,
                                'family_type': base_child_type,
                                'group': g.get('name'),
                                'x': cx, 'y': cy, 'w': cw, 'h': ch,
                                **({'label': display_label} if display_label else {}),
                                'provenance': {
                                    'source_file': os.path.relpath(screen_file, self.base_dir),
                                    'include_chain': include_chain,
                                    'ganged_parent': t,
                                    'parent_group': g.get('name'),
                                    'preference_key': pref_child_key,
                                    'family_type': base_child_type,
                                    'concrete_type': concrete_type,
                                }
                            })
                            if 'horizontal' in gang_type:
                                group_x += group_width + hgap
                            else:
                                group_y += group_height + vgap
                        if 'horizontal' in gang_type:
                            group_x += gap_size
                        else:
                            group_y += gap_size
                else:
                    r = type_ratio(t)
                    if r:
                        bw, bh, bx, by = bounding_box(width, height, x, y, r)
                        width, height, x, y = bw, bh, bx, by
                    # For non-ganged instruments, also honor preference gauge type override
                    concrete_type = t
                    if pref_key and isinstance(self.preferences.get('gauges'), dict):
                        gspec = self.preferences['gauges'].get(pref_key)
                        if isinstance(gspec, dict) and gspec.get('type'):
                            concrete_type = str(gspec.get('type')).strip()
                    display_label = _label_for(concrete_type, inst)
                    if not display_label and 'button' in str(concrete_type).lower():
                        display_label = _button_summary_from_options(inst.get('options') or {}, cur_dir)
                    items_out.append({
                        'type': concrete_type,
                        'family_type': t,
                        'x': x, 'y': y, 'w': width, 'h': height,
                        **({'label': display_label} if display_label else {}),
                        'provenance': {
                            'source_file': os.path.relpath(screen_file, self.base_dir),
                            'include_chain': include_chain,
                            'ganged_parent': None,
                            'parent_group': None,
                            'preference_key': pref_key,
                            'family_type': t,
                            'concrete_type': concrete_type,
                        }
                    })
            return {'width': int(W), 'height': int(H), 'items': items_out}
        
        def dedupe(items: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
            # Deprecated: kept temporarily for compatibility; do not use.
            return items

        def annotate_duplicates(items: List[Dict[str,Any]]) -> None:
            """Mark items that have exact overlapping duplicates (same type/group/x/y/w/h) with duplicates=<count-1>.
            Does not remove or move any items."""
            by_key: Dict[Tuple, List[Dict[str,Any]]] = {}
            for it in items:
                key = (
                    it.get('type'),
                    it.get('group'),
                    round(float(it.get('x',0)),2),
                    round(float(it.get('y',0)),2),
                    round(float(it.get('w',0)),2),
                    round(float(it.get('h',0)),2)
                )
                by_key.setdefault(key, []).append(it)
            for items_list in by_key.values():
                if len(items_list) > 1:
                    count = len(items_list) - 1
                    for it in items_list:
                        it['duplicates'] = count

        # Collect buttons from config/buttons
        buttons_dir = os.path.join(self.base_dir, 'buttons')
        def _extract_symbols(expr: str) -> List[str]:
            if not isinstance(expr, str):
                return []
            # crude tokenizer: split by non-alnum underscores and filter uppercase tokens
            import re
            tokens = re.split(r"[^A-Za-z0-9_\.]+", expr)
            syms = []
            for t in tokens:
                if not t:
                    continue
                # Skip operators/keywords
                if t.lower() in ('and','or','not','eq','ne','lt','gt','le','ge','true','false','clicked','previous_condition'):
                    continue
                # Allow dotted annunciate style, capture before dot
                base = t.split('.',1)[0]
                if base and base.isupper():
                    syms.append(base)
            return sorted(list(dict.fromkeys(syms)))

        if os.path.isdir(buttons_dir):
            for name in sorted(os.listdir(buttons_dir)):
                p = os.path.join(buttons_dir, name)
                if os.path.isdir(p):
                    continue
                if not name.endswith('.yaml'):
                    continue
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        bdoc = yaml.safe_load(f) or {}
                except Exception:
                    continue
                if not isinstance(bdoc, dict):
                    continue
                stem = os.path.splitext(name)[0]
                label = bdoc.get('label') or bdoc.get('text') or stem
                btn = {
                    'id': stem,
                    'file': os.path.relpath(p, self.base_dir),
                    'type': bdoc.get('type'),
                    'label': label,
                    'dbkey': bdoc.get('dbkey'),
                    'conditions': [],
                    'actions': [],
                    'provenance': {
                        'source_file': os.path.relpath(p, self.base_dir),
                        'include_chain': [],
                    }
                }
                conds = bdoc.get('conditions') or []
                for c in conds:
                    when = (c or {}).get('when')
                    actions = (c or {}).get('actions') or []
                    btn['conditions'].append({
                        'when': when,
                        'symbols': _extract_symbols(when),
                        'actions': actions,
                        'continue': (c or {}).get('continue', False)
                    })
                    btn['actions'].extend(actions)
                normalized['buttons'].append(btn)

        if os.path.isdir(screens_dir):
            for name in sorted(os.listdir(screens_dir)):
                if not name.endswith('.yaml'):
                    continue
                sf = os.path.join(screens_dir, name)
                try:
                    with open(sf, 'r', encoding='utf-8') as f:
                        doc = yaml.safe_load(f) or {}
                    if not isinstance(doc, dict):
                        continue
                    # Screen key is the first mapping key
                    if len(doc) == 0:
                        continue
                    skey = next(iter(doc.keys()))
                    sbody = doc[skey]
                    if isinstance(sbody, dict) and 'layout' in sbody and 'instruments' in sbody:
                        normalized['screens'].append({
                            'name': skey,
                            'file': os.path.relpath(sf, self.base_dir),
                            'expanded': self.expand_screen(sbody, sf),
                            'geometry': (lambda g: (annotate_duplicates(g['items']) or g))(compute_geometry(sbody, sf)),
                        })
                except Exception:
                    continue

        return normalized


def main():
    ap = argparse.ArgumentParser(description='pyEfis Configuration Normalizer')
    ap.add_argument('--config', default=os.path.join('config', 'default.yaml'), help='Path to config/default.yaml')
    ap.add_argument('--base', default=os.path.join('config'), help='Base config directory')
    ap.add_argument('--out', default=os.path.join('tools', 'cfg_explorer', 'normalized_config.json'), help='Output JSON path')
    ap.add_argument('--define', action='append', default=[], help='Define a symbol for conditional disabled evaluation (e.g., --define BUTTONS=true). Can be repeated.')
    args = ap.parse_args()

    base_dir = os.path.abspath(args.base)
    default_yaml = os.path.abspath(args.config)

    if not os.path.exists(default_yaml):
        print(f"Error: cannot find config file: {default_yaml}", file=sys.stderr)
        sys.exit(2)

    prefs = load_preferences(base_dir)
    # Parse defines to booleans; values: true/false/1/0/yes/no; if value omitted, default to true
    defines: Dict[str, bool] = {}
    for entry in (args.define or []):
        if entry is None:
            continue
        if '=' in entry:
            k, v = entry.split('=', 1)
            k = k.strip()
            v = v.strip().lower()
            defines[k] = v in ('1','true','yes','on')
        else:
            defines[entry.strip()] = True
    norm = Normalizer(base_dir, prefs, defines=defines)
    data = norm.normalize(default_yaml)

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Wrote normalized JSON: {out_path}")


if __name__ == '__main__':
    main()
