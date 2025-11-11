#!/usr/bin/env python3

"""
Config Inspector Plus: Visualize buttons, conditions, and action handlers.

Adds to the original inspector by:
- Parsing config/buttons/*.yaml to extract button definitions
- Showing per-button conditions (when/continue) and actions
- Resolving action handlers (from pyefis.hmi.actionclass.ActionClass.signalMap)
- Visualizing relationships: Button -> FIX deps (from condition_keys and tokens) and Button -> Action handlers / DB targets

Run standalone:
  python3 tools/config_inspector_plus.py

Optional args:
  --buttons-dir <path>        # defaults to repo config/buttons
  --include-style-actions     # show styling actions in the graph (default off)
"""

from __future__ import annotations

import os
import re
import sys
import glob
import argparse
import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QPen, QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeView,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QComboBox,
)

# ---------------- Data structures ----------------

@dataclass
class ActionDef:
    name: str
    args: Any

@dataclass
class ConditionDef:
    when: Any
    continue_: bool = False
    actions: List[ActionDef] = field(default_factory=list)
    deps_exact: Set[str] = field(default_factory=set)
    deps_prefix: Set[str] = field(default_factory=set)

@dataclass
class ButtonDef:
    file_path: str
    name: str
    dbkey: str
    type: str
    condition_keys: List[str] = field(default_factory=list)
    conditions: List[ConditionDef] = field(default_factory=list)

# ---------------- Parsing helpers ----------------

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*")

STYLE_ACTIONS = {
    'set bg color', 'set fg color', 'set text', 'button'
}

DB_ACTIONS = {
    'set value', 'change value', 'toggle bit'
}


def parse_buttons(buttons_dir: str) -> List[ButtonDef]:
    buttons: List[ButtonDef] = []
    for fp in sorted(glob.glob(os.path.join(buttons_dir, "*.yaml"))):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue
        btype = data.get('type', '')
        text = str(data.get('text', '') or '').strip()
        dbkey = str(data.get('dbkey', '') or '').strip()
        cond_keys = list(data.get('condition_keys', []) or [])
        conditions = []
        for cond in (data.get('conditions', []) or []):
            w = cond.get('when')
            cont = bool(cond.get('continue', False))
            acts = []
            for act in (cond.get('actions', []) or []):
                if isinstance(act, dict):
                    for k, v in act.items():
                        acts.append(ActionDef(name=str(k), args=v))
            c = ConditionDef(when=w, continue_=cont, actions=acts)
            # derive deps from 'when' string if applicable
            if isinstance(w, str):
                tokens = set(TOKEN_RE.findall(w))
                for t in tokens:
                    if t.endswith('.'):
                        c.deps_prefix.add(t)
                    elif t.endswith('.aux'):
                        c.deps_prefix.add(t + '.')
                    else:
                        c.deps_exact.add(t)
            conditions.append(c)
        buttons.append(ButtonDef(
            file_path=fp,
            name=text or os.path.basename(fp),
            dbkey=dbkey,
            type=btype,
            condition_keys=cond_keys,
            conditions=conditions,
        ))
    return buttons

# ---------------- Action registry ----------------

try:
    from pyefis.hmi.actionclass import ActionClass
    ACTIONS_AVAILABLE = True
except Exception:
    ActionClass = None  # type: ignore
    ACTIONS_AVAILABLE = False


def get_action_names() -> Set[str]:
    if not ACTIONS_AVAILABLE:
        return set()
    try:
        inst = ActionClass()
        return set(inst.signalMap.keys())
    except Exception:
        return set()

# ---------------- Models ----------------

class ButtonsTreeModel:
    def __init__(self, buttons: List[ButtonDef], action_names: Set[str]):
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Node", "Details", "Notes"])
        root = QStandardItem("Buttons")
        root.setEditable(False)
        self.model.appendRow([root, QStandardItem(""), QStandardItem("")])
        for b in buttons:
            b_item = QStandardItem(f"{b.name}")
            b_item.setEditable(False)
            details = QStandardItem(f"type={b.type} dbkey={b.dbkey}")
            notes = QStandardItem(os.path.relpath(b.file_path, start=os.path.dirname(buttons[0].file_path)) if buttons else "")
            root.appendRow([b_item, details, notes])
            # condition keys
            ck_parent = QStandardItem("condition_keys")
            ck_parent.setEditable(False)
            b_item.appendRow([ck_parent, QStandardItem(f"{len(b.condition_keys)} keys"), QStandardItem("")])
            for k in b.condition_keys:
                ck_parent.appendRow([QStandardItem(k), QStandardItem(""), QStandardItem("")])
            # conditions
            cond_parent = QStandardItem("conditions")
            cond_parent.setEditable(False)
            b_item.appendRow([cond_parent, QStandardItem(f"{len(b.conditions)}"), QStandardItem("")])
            for idx, c in enumerate(b.conditions):
                when_text = str(c.when)
                node = QStandardItem(f"[{idx}] when: {when_text}")
                node.setEditable(False)
                cont_item = QStandardItem("continue: true" if c.continue_ else "continue: false")
                cond_parent.appendRow([node, cont_item, QStandardItem("")])
                # deps
                dep_parent = QStandardItem("deps")
                dep_parent.setEditable(False)
                node.appendRow([dep_parent, QStandardItem(""), QStandardItem("")])
                for d in sorted(c.deps_exact):
                    dep_parent.appendRow([QStandardItem(d), QStandardItem("exact"), QStandardItem("")])
                for d in sorted(c.deps_prefix):
                    dep_parent.appendRow([QStandardItem(d), QStandardItem("prefix"), QStandardItem("")])
                # actions
                act_parent = QStandardItem("actions")
                act_parent.setEditable(False)
                node.appendRow([act_parent, QStandardItem(f"{len(c.actions)}"), QStandardItem("")])
                for a in c.actions:
                    a_name = a.name.strip()
                    a_name_lc = a_name.lower()
                    kind = (
                        "style" if a_name_lc in STYLE_ACTIONS else
                        "db" if a_name_lc in DB_ACTIONS else
                        ("hmi" if a_name_lc in (an.lower() for an in action_names) else "unknown")
                    )
                    act_parent.appendRow([
                        QStandardItem(a_name),
                        QStandardItem(str(a.args)),
                        QStandardItem(kind),
                    ])

# ---------------- Graph view ----------------

class RelationshipGraph(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(self.renderHints())
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.include_style = False

    def set_include_style(self, include: bool):
        self.include_style = include

    def draw_for_button(self, b: ButtonDef, action_names: Set[str]):
        self.scene.clear()
        # Collect dependencies and actions per button
        dep_keys: Set[str] = set(b.condition_keys)
        for c in b.conditions:
            dep_keys.update(c.deps_exact)
            # prefix deps are included as-is
            dep_keys.update(c.deps_prefix)
        dep_keys = {d for d in dep_keys if d}

        hmi_actions: Set[str] = set()
        db_targets: Set[str] = set()
        style_actions: Set[str] = set()
        for c in b.conditions:
            for a in c.actions:
                name_lc = a.name.lower()
                if name_lc in STYLE_ACTIONS:
                    style_actions.add(a.name)
                elif name_lc in DB_ACTIONS:
                    # Try to extract DB key from args (format "KEY, value")
                    if isinstance(a.args, str):
                        parts = a.args.split(',')
                        if parts:
                            db_targets.add(parts[0].strip())
                    else:
                        db_targets.add(str(a.args))
                else:
                    # HMI handler?
                    for an in action_names:
                        if an.lower() == name_lc:
                            hmi_actions.add(an)
                            break

        # Simple column layout
        x_button = 20
        x_dep = 320
        x_act = 670
        y = 20

        def draw_node(x, y, text, color):
            padding = 8
            font = QFont("DejaVu Sans", 9)
            item_text = QGraphicsTextItem(text)
            item_text.setFont(font)
            self.scene.addItem(item_text)
            br = item_text.boundingRect()
            rect = QRectF(0, 0, br.width() + padding*2, br.height() + padding*2)
            rect_item = QGraphicsRectItem(rect)
            rect_item.setBrush(QBrush(QColor(color)))
            rect_item.setPen(QPen(Qt.GlobalColor.black))
            rect_item.setPos(x, y)
            self.scene.addItem(rect_item)
            item_text.setPos(x + padding, y + padding)
            # Ensure text is rendered above rectangle even if insertion order changes
            rect_item.setZValue(0)
            item_text.setZValue(1)
            return rect_item, rect

        # Button node
        btn_node, btn_rect = draw_node(x_button, y, f"Button: {b.name}\n{os.path.basename(b.file_path)}\n{b.type} {b.dbkey}", "#F0F8FF")

        # Dependencies stack
        dep_nodes: List[Tuple[QGraphicsRectItem, QRectF]] = []
        dy = y
        for d in sorted(dep_keys):
            node, r = draw_node(x_dep, dy, d, "#FFFDE7")
            dep_nodes.append((node, r))
            dy += r.height() + 12

        # Actions stack
        act_nodes: List[Tuple[QGraphicsRectItem, QRectF]] = []
        dy = y
        for a in sorted(hmi_actions):
            node, r = draw_node(x_act, dy, f"HMI: {a}", "#E3F2FD")
            act_nodes.append((node, r))
            dy += r.height() + 8
        for d in sorted(db_targets):
            node, r = draw_node(x_act, dy, f"DB: {d}", "#FCE4EC")
            act_nodes.append((node, r))
            dy += r.height() + 8
        if self.include_style:
            for s in sorted(style_actions):
                node, r = draw_node(x_act, dy, f"STYLE: {s}", "#EEEEEE")
                act_nodes.append((node, r))
                dy += r.height() + 8

        # Connectors (simple straight lines)
        pen = QPen(QColor("#888"))
        for node, r in dep_nodes:
            p1 = QPointF(btn_node.pos().x() + btn_rect.width(), btn_node.pos().y() + btn_rect.height()/2)
            p2 = QPointF(node.pos().x(), node.pos().y() + r.height()/2)
            self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
        for node, r in act_nodes:
            p1 = QPointF(btn_node.pos().x() + btn_rect.width(), btn_node.pos().y() + btn_rect.height()/2)
            p2 = QPointF(node.pos().x(), node.pos().y() + r.height()/2)
            self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)

        # Resize scene rect
        self.scene.setSceneRect(0, 0, x_act + 400, max(dy + 40, y + btn_rect.height() + 40))

# ---------------- Main Window ----------------

class InspectorPlusWindow(QMainWindow):
    def __init__(self, buttons: List[ButtonDef], action_names: Set[str]):
        super().__init__()
        self.setWindowTitle("pyEfis Buttons/Actions Inspector")
        self.resize(1200, 800)
        self.buttons = buttons
        self.action_names = action_names

        splitter = QSplitter(self)
        left = QWidget(self)
        left_v = QVBoxLayout(left)
        left.setLayout(left_v)

        # Filters
        filt_row = QWidget(self)
        filt_layout = QHBoxLayout(filt_row)
        filt_row.setLayout(filt_layout)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Filter by button name or dbkey")
        filt_layout.addWidget(QLabel("Filter:"))
        filt_layout.addWidget(self.search)
        left_v.addWidget(filt_row)

        # Tree model
        self.tree = QTreeView(self)
        self.model_builder = ButtonsTreeModel(buttons, action_names)
        self.tree.setModel(self.model_builder.model)
        self.tree.expandToDepth(1)
        self.tree.selectionModel().selectionChanged.connect(self._on_selection)
        left_v.addWidget(self.tree, 1)

        # Right: Graph + options
        right = QWidget(self)
        right_v = QVBoxLayout(right)
        right.setLayout(right_v)
        opt_row = QWidget(self)
        opt_l = QHBoxLayout(opt_row)
        opt_row.setLayout(opt_l)
        opt_l.addWidget(QLabel("Show style actions:"))
        self.style_combo = QComboBox(self)
        self.style_combo.addItems(["No", "Yes"])
        opt_l.addWidget(self.style_combo)
        right_v.addWidget(opt_row)

        self.graph = RelationshipGraph(self)
        right_v.addWidget(self.graph, 1)

        self.style_combo.currentTextChanged.connect(self._redraw)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        # Select first button if available
        if buttons:
            self.tree.setCurrentIndex(self.model_builder.model.index(0, 0))

    def _find_button_by_item(self, item: QStandardItem) -> Optional[ButtonDef]:
        # Top-level root is "Buttons", children are buttons
        if item.parent() is None:
            return None
        # Walk up to button node: parent's parent is root
        while item.parent() and item.parent().parent() is not None:
            item = item.parent()
        btn_name = item.text()
        for b in self.buttons:
            if b.name == btn_name:
                return b
        return None

    def _on_selection(self, *_):
        idxs = self.tree.selectionModel().selectedRows(0)
        if not idxs:
            return
        idx = idxs[0]
        item = self.model_builder.model.itemFromIndex(idx)
        b = self._find_button_by_item(item)
        if b:
            self._draw_button(b)

    def _redraw(self, *_):
        idxs = self.tree.selectionModel().selectedRows(0)
        if not idxs:
            return
        idx = idxs[0]
        item = self.model_builder.model.itemFromIndex(idx)
        b = self._find_button_by_item(item)
        if b:
            self._draw_button(b)

    def _draw_button(self, b: ButtonDef):
        include_style = (self.style_combo.currentText() == "Yes")
        self.graph.set_include_style(include_style)
        self.graph.draw_for_button(b, self.action_names)

# ---------------- Entry point ----------------

def default_buttons_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', 'config', 'buttons'))


def main():
    ap = argparse.ArgumentParser(description="pyEfis Buttons/Actions Inspector")
    ap.add_argument('--buttons-dir', default=default_buttons_dir(), help='Path to config/buttons directory')
    ap.add_argument('--include-style-actions', action='store_true', help='Include styling actions in the graph')
    args = ap.parse_args()

    buttons = parse_buttons(args.buttons_dir)
    # Create QApplication BEFORE any QWidget subclass (ActionClass) is instantiated
    app = QApplication(sys.argv)
    action_names = get_action_names()
    w = InspectorPlusWindow(buttons, action_names)
    if args.include_style_actions:
        w.style_combo.setCurrentText('Yes')
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
