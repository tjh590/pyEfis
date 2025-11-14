#  Copyright (c) 2023 Eric Blevins
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
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# This implements a dynamice interactive button.
# It can change states based on data in FIX, it can display data and act as a button for user iput.
# 
import time
import threading
import pycond as pc

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

import logging
import pyavtools.fix as fix
logger=logging.getLogger(__name__)

import yaml
import os
import pathlib
import re
from pyefis import hmi
import time
from pyefis.instruments import helpers

class Button(QWidget):
    def __init__(self, parent=None, config_file=None, font_family="DejaVu Sans Condensed"):
        super(Button, self).__init__(parent)

        self.parent = parent
        self.font_family = font_family
        self.font_mask = None
        self.font_size = None
        config = yaml.load(open(config_file), Loader=yaml.SafeLoader)
        # Raw conditions from config; will be pre-compiled for efficiency.
        self._conditions = config.get('conditions', [])
        self.config = config
        self._button = QPushButton(self)  # self.config['text'], self)
        self._style = dict()
        self._style['bg'] = QColor(self.config.get('bg_color', 'lightgray'))
        self._style['fg'] = QColor(self.config.get('fg_color', 'black'))
        self._style['transparent'] = self.config.get('transparent', False)
        self._buttonhide = self.config.get('hover_show', False)
        self._title = ""
        self._toggle = False
        # Style/eval diagnostics and caches
        self._last_style = {
            'bg': None,
            'fg': None,
            'transparent': None,
            'border_size': None,
            'font_size': None,
            'enabled': None,
            'checked': None,
            'stylesheet_key': None,
        }
        self._diag_eval_total = 0
        self._diag_eval_matched = 0
        self._diag_eval_skipped = 0
        self._diag_styles_applied = 0
        self._diag_styles_noop = 0
        self._diag_hmi_actions = 0
        # Repalce {id} in the dbkey so we can have different 
        # button names per node without having 
        # to duplicate all buttons.
        self._dbkey = fix.db.get_item(self.config['dbkey'].replace('{id}', str(self.parent.parent.nodeID)))
        time.sleep(0.01)
        #self._button.setChecked(self._dbkey.value)

        #self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)

        self._repeat = False
        if self.config['type'] == 'toggle':
            self._toggle = True
            self._button.setCheckable(True)
            # toggled reacts to setChecked where clicked does not
            # Helps to prevent erronious recursion
            # However not using toggled for toggle buttons breaks
            # things such as encoder navigation
            self._button.toggled.connect(self.buttonToggled)

        elif self.config['type'] == 'simple':
            self._button.setCheckable(False)
            self._button.clicked.connect(self.buttonToggled)
        elif self.config['type'] == 'repeat':
            self._repeat = True
            self._button.pressed.connect(self.buttonToggled)
            self._button.setAutoRepeat(True)
            self._button.setAutoRepeatInterval(self.config.get('repeat_interval', 300))
            self._button.setAutoRepeatDelay(self.config.get('repeat_delay', 300))
        else:
            raise SyntaxError(f"Unknown button type '{self.config['type']}'")
        self._button.setEnabled(True)
        #self._dbkey = fix.db.get_item(self.config['dbkey'])
        #self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)

        self._db = dict() #All the fix db items
        self._db_data = dict() #All the fix db data for use in pycond
        self.condition_keys = self.config.get('condition_keys', [])
        self._conditions_timer = QTimer(self)
        self._conditions_timer.setSingleShot(True)
        self._conditions_timer.timeout.connect(self._executePendingConditions)
        self._pending_clicked = False  # Whether any pending scheduled evaluation originated from a click/toggle.
        # Allow configurable coalescing interval (ms). Default 0 = next event loop.
        self._conditions_interval_ms = int(self.config.get('conditions_debounce_ms', 0))

        # Optional periodic diagnostics logging if debug enabled
        self._diag_timer = None
        if logger.isEnabledFor(logging.DEBUG):
            self._diag_timer = QTimer(self)
            self._diag_timer.setInterval(1000)
            self._diag_timer.timeout.connect(self._logDiagnostics)
            self._diag_timer.start()

        self.initDB()
        self._compileConditionsOnce()
        self.setStyle('set text', self.config['text'])
        # On startup set button back to proper state
        self._button.setChecked(self._dbkey.value)
        self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)
        # Initial evaluation (visible state may still be False but we need first pass for text substitutions)
        self.processConditions()

    def enterEvent(self, QEvent):
        if self._buttonhide:
            # Show menu if hover over it
            fix.db.set_value('HIDEBUTTON', False)

    def isEnabled(self):
        return self._button.isEnabled()

    def initDB(self):
        
        # init self._db and connect to signals
        for key in self.condition_keys:
            self._db[key] = fix.db.get_item(key)
            # Setup connections first
            self._db[key].valueChanged[bool].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
            self._db[key].valueChanged[int].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
            self._db[key].valueChanged[str].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
            self._db[key].valueChanged[float].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))

            self._db[key].oldChanged.connect(lambda oldChanged, key=key, signal='old': self.dataChanged(key=key,signal=signal))
            self._db[key].badChanged.connect(lambda badChanged, key=key, signal='bad': self.dataChanged(key=key,signal=signal))
            self._db[key].failChanged.connect(lambda failChanged, key=key, signal='fail': self.dataChanged(key=key,signal=signal))
            self._db[key].annunciateChanged.connect(lambda annunciateChanged, key=key, signal='annunciate': self.dataChanged(key=key,signal=signal))
            self._db[key].auxChanged.connect(lambda auxChanged, key=key, signal='aux': self.dataChanged(key=key,signal=signal))

            self._db_data[key] = self._db[key].value
            self._db_data[f"{key}.old"] = self._db[key].old
            self._db_data[f"{key}.bad"] = self._db[key].bad
            self._db_data[f"{key}.fail"] = self._db[key].fail
            self._db_data[f"{key}.annunciate"] = self._db[key].annunciate
            for aux in self._db[key].aux:
                self._db_data[f"{key}.aux.{aux}"] = self._db[key].aux[aux]
        self._db_data[self._dbkey.key] = self._dbkey.value
        time.sleep(0.01)

    def dataChanged(self,key=None,signal=None):
        """Slot for any FIX item change relevant to this button.

        Previous implementation immediately re-parsed and evaluated all conditions.
        We now only update the cached state and schedule a coalesced evaluation
        (unless the button is hidden, in which case we skip entirely to reduce CPU).
        """
        logger.warning(f"dataChanged key={key} signal={signal}")
        if key in self._db:
            if signal == 'value':
                self._db_data[key] = self._db[key].value
            elif signal == 'old':
                self._db_data[f"{key}.old"] = self._db[key].old
            elif signal == 'bad':
                self._db_data[f"{key}.bad"] = self._db[key].bad
            elif signal == 'fail':
                self._db_data[f"{key}.fail"] = self._db[key].fail
            elif signal == 'annunciate':
                self._db_data[f"{key}.annunciate"] = self._db[key].annunciate
            elif signal == 'aux':
                for aux in self._db[key].aux:
                    self._db_data[f"{key}.aux.{aux}"] = self._db[key].aux[aux]
        # If the button isn't visible, skip condition evaluation entirely to avoid hot path churn.
        if not self.isVisible():
            return
        self._scheduleConditionsEvaluation(clicked=False)

    def resizeEvent(self,event):
        self._button.resize(self.width(), self.height())
        self.font_size = None
        self.setStyle()

    def setTitle(self, title):
        if self._title != title:
            self._title = title
            for t,d in self._db_data.items():
                self._title = re.sub(f"{{{t}}}", str(d), self._title)
            self._button.setText(self._title)

    def getTitle(self):
        return self._title

    title = property(getTitle,setTitle)

    def buttonToggled(self):
        # Button can be toggled by _dbkey or by clicking the button
        # Make sure they stay in sync
        logger.debug(f"{self._button.text()}:buttonToggled:self._button.isChecked({self._button.isChecked()})")
        if not self.isVisible(): return

        # Toggle button toggled
        if self._toggle and self._button.isChecked() != self._dbkey.value:
            with QSignalBlocker(self._dbkey):
                fix.db.set_value(self._dbkey.key, self._button.isChecked())
                self._dbkey.output_value()
            # Now we evaluate conditions and update the button style/text/state
            # Immediate evaluation for user action
            self.processConditions(True)

        elif not self._toggle:
            # Simple button
            self.processConditions(True)


    def dbkeyChanged(self,data):
        if self._dbkey.bad:
            return
        # The same button configuration might be used on multiple screens
        # Only buttons on the active screen should be changing.
        logger.debug(f"{self._button.text()}:dbkeyChanged:data={data}:self._button.isChecked({self._button.isChecked()})")
        self._db_data[self._dbkey.key] = self._dbkey.value
        #self._dbkey.output_value()

        if not self.isVisible(): return
        #self._db_data[self._dbkey.key] = self._dbkey.value
        if self._toggle and self._button.isChecked() == self._dbkey.value:
            #This is a recursive call do nothing
            logger.debug(f"{self._button.text()}:recursive:data={data}:self._button.isChecked({self._button.isChecked()})")
            return
        else:
            logger.debug(f"{self._button.text()}:toggled:data={data}:self._button.isChecked({self._button.isChecked()})")
            if not self._repeat and not self._toggle:
                # Only take action if changing from False to True
                if not self._dbkey.value: 
                    logger.debug(f"Data is: {data}")
                    return

                logger.debug(f"data:{data} self._dbkey.value:{self._dbkey.value}")
                # Block signal to prevent recursive call
                with QSignalBlocker(self._dbkey):
                    self._dbkey.value = False
            self._button.setChecked(self._dbkey.value) 
            self.processConditions(True)
            if self._repeat:
                # Send press even while true, send release event when false
                # Physical button would need to only set True while button is pressed, then set to False when released
                if self._dbkey.value:
                    event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(0,0), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier);
                else:
                    event = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(0,0), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier);
                QApplication.sendEvent(self._button, event);

    def showEvent(self,event):
        self.processConditions()
        # Do we need to only do this for toggle buttons?
        if self._toggle: 
            self._button.setChecked(self._dbkey.value)

    def _compileConditionsOnce(self):
        """Pre-compile string 'when' conditions into callable form to avoid per-update parsing.

        Stores compiled function in cond['_fn'].
        """
        for cond in self._conditions:
            w = cond.get('when')
            logger.warning(f"Compiling condition: {w}")
            if isinstance(w, str) and '_fn' not in cond:
                try:
                    # Normalization: if the entire expression is a single quoted identifier
                    # (e.g., "HIDEBUTTON" or 'HIDEBUTTON'), strip the quotes so it is
                    # interpreted as the variable HIDEBUTTON rather than a string literal.
                    m = re.match(r"^\s*([\"'])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\1\s*$", w)
                    logger.warning(f"Normalizing condition: {m}")
                    if m:
                        w = m.group(2)
                        cond['when'] = w
                        logger.warning(f"Condition normalized from quoted to unquoted identifier: '{cond['when']}'")
                    tokens = pc.tokenize(w, sep=' ', brkts='[]')
                    logger.warning(f"Compiling condition tokens: {tokens}")
                    expr = pc.to_struct(tokens)
                    cond['_fn'] = pc.pycond(expr)
                    # Build a dependency set by extracting token-like identifiers
                    # This is a conservative regex; it will include names that look like KEY or KEY.suffix
                    deps = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*", w))
                    cond['_deps_exact'] = set()
                    cond['_deps_prefix'] = set()
                    for d in deps:
                        if d.endswith('.'):
                            cond['_deps_prefix'].add(d)
                        elif d.endswith('.aux'):
                            # Support aux prefix references like KEY.aux
                            cond['_deps_prefix'].add(d + '.')
                        else:
                            cond['_deps_exact'].add(d)
                except Exception as e:
                    logger.warning(f"Failed to pre-compile condition '{w}': {e}")

    def _scheduleConditionsEvaluation(self, clicked=False):
        """Coalesce rapid updates into a single evaluation using a short single-shot timer."""
        # Preserve clicked flag if any pending evaluation originated from a click.
        self._pending_clicked = self._pending_clicked or clicked
        if not self._conditions_timer.isActive():
            # 0 ms (next event loop iteration) keeps UI responsive while collapsing bursts.
            self._conditions_timer.start(self._conditions_interval_ms)

    def _executePendingConditions(self):
        logger.warning(f"_executePendingConditions")
        pc_flag = self._pending_clicked
        self._pending_clicked = False
        self.processConditions(clicked=pc_flag)

    def processConditions(self,clicked=False):
        self._db_data['SCREEN'] = self.parent.screenName
        self._db_data['CLICKED'] = clicked
        self._db_data['DBKEY'] = self._dbkey.value 
        self._db_data["PREVIOUS_CONDITION"] = False
        logger.debug(f"{self._dbkey.key}:{self._dbkey.value}")
        self._diag_eval_total += 1
        for cond in self._conditions:
            if 'when' in cond:
                if type(cond['when']) == str:
                    fn = cond.get('_fn')
                    if fn is None:
                        # Fallback for any condition added dynamically after init.
                        try:
                            wdyn = cond['when']
                            # Apply the same normalization as compile-once: if the entire
                            # expression is a single quoted identifier, strip the quotes.
                            m = re.match(r"^\s*([\"'])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\1\s*$", wdyn)
                            if m:
                                wdyn = m.group(2)
                                cond['when'] = wdyn
                            tokens = pc.tokenize(wdyn, sep=' ', brkts='[]')
                            expr = pc.to_struct(tokens)
                            fn = pc.pycond(expr)
                            cond['_fn'] = fn
                            # minimal deps on dynamic add
                            cond['_deps_exact'] = set()
                            cond['_deps_prefix'] = set()
                        except Exception as e:
                            logger.warning(f"Dynamic compile failed for condition '{cond['when']}': {e}")
                            continue
                    if fn(state=self._db_data) is True:
                        self._diag_eval_matched += 1
                        self._db_data["PREVIOUS_CONDITION"] = True
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} = True")
                        self.processActions(cond['actions'])
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} conditions processed")
                        if not cond.get('continue', False): 
                            logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} Does not continue")
                            return
                        else:
                            logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} continues")
                    else:
                        self._db_data["PREVIOUS_CONDITION"] = False
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} = False")
                elif type(cond['when']) == bool:
                    if cond['when']:
                        if self._button.isChecked() or self._toggle == False:
                            self.processActions(cond['actions'])
                            if not cond.get('continue', False): return
                    else:
                        if not self._button.isChecked():
                            self.processActions(cond['actions'])
                            if not cond.get('continue', False): return
                else:
                    raise SyntaxError(f"condition must be a string or boolean, not: {cond['when']}")
            else:
                raise SyntaxError(f"Unknown confition: {cond}")           
    def processActions(self,actions):
        for act in actions:
            for action,args in act.items():
                # Prevent recursive calls to self
                with QSignalBlocker(self._dbkey):
                    handler = hmi.actions.findAction(action)
                    if handler is not None:
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:HMI:{action}:{args} Tried")
                        hmi.actions.trigger(action, args)
                        self._diag_hmi_actions += 1
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:HMI:{action}:{args} Success")
                    else:
                        self.setStyle(action,args)
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:STYLE:{action}:{args}")

    def setStyle(self,action='',args=None):

        if action.lower() == 'set bg color':
            self._style['bg'] = QColor(args)
        elif action.lower() == 'set fg color':
            self._style['fg'] = QColor(args)
        elif action.lower() == 'set text':
            self.setTitle(args)
        elif action.lower() == 'button':
            if args.lower() == 'disable':
              if self._last_style['enabled'] is not False:
                  self._button.setEnabled(False)
                  self._last_style['enabled'] = False
            elif args.lower() == 'enable':
              if self._last_style['enabled'] is not True:
                  self._button.setEnabled(True)
                  self._last_style['enabled'] = True
            elif args.lower() == 'checked' and not self._button.isChecked():
                self._button.blockSignals(True)
                self._button.setChecked(True)
                self._dbkey.value = True
                self._dbkey.output_value()
                self._button.blockSignals(False)
                self._last_style['checked'] = True

            elif args.lower() == 'unchecked' and self._button.isChecked():
                self._button.blockSignals(True)
                self._button.setChecked(False)
                self._dbkey.value = False
                self._dbkey.output_value()
                self._button.blockSignals(False)
                self._last_style['checked'] = False


        # Compute border size
        border_size = qRound(self._button.height() * 6/100)
        self._style['border_size'] = border_size
        # Prepare font; calculate only when mask present and size unknown
        self.font = QFont(self.font_family)
        if self.font_mask:
            if not self.font_size:
                self.font_size = helpers.fit_to_mask(
                    self.width() - (border_size*2.5),
                    self.height() - (border_size*2.5),
                    self.font_mask,
                    self.font_family,
                )
            self.font.setPointSizeF(self.font_size)
        else:
            desired_px = qRound(self.height() * 38/100)
            if self._last_style['font_size'] != desired_px:
                self.font.setPixelSize(desired_px)
                self._last_style['font_size'] = desired_px
            else:
                # Reuse previous font size
                self.font.setPixelSize(self._last_style['font_size'])
        bg_color = self._style.get('bg_override', None) or self._style['bg']
        # Create a small stylesheet key to detect no-ops
        ss_key = (
            bg_color.name(),
            self._style['fg'].name(),
            self._style['transparent'],
            border_size,
        )
        if ss_key != self._last_style['stylesheet_key']:
            if self._style['transparent']:
                self._button.setStyleSheet(
                    f"QPushButton {{border: 1px solid {bg_color.name()}; background: transparent;border-radius: 6px}}"
                )
            else:
                self._button.setStyleSheet(
                    f"QPushButton {{border: 2px solid {bg_color.darker(150).name()};border-radius: 10%; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_color.lighter(130).name()}, stop: 1 {bg_color.name()});border-style: outset; border-width: {border_size}px;color:{self._style['fg'].name()}}} "
                    f"QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_color.name()}, stop: 1 {bg_color.lighter(190).name()});border-style:inset}} "
                    f"QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_color.name()}, stop: 1 {bg_color.lighter(190).name()});border-style:inset}}"
                )
            self._last_style['stylesheet_key'] = ss_key
            self._last_style['bg'] = bg_color.name()
            self._last_style['fg'] = self._style['fg'].name()
            self._last_style['transparent'] = self._style['transparent']
            self._last_style['border_size'] = border_size
            self._diag_styles_applied += 1
        else:
            self._diag_styles_noop += 1
        # Apply font only if it differs
        self._button.setFont(self.font)

    def _logDiagnostics(self):
        logger.debug(
            f"ButtonDiag title='{self._title}' key='{self._dbkey.key}': eval_total={self._diag_eval_total} matched={self._diag_eval_matched} "
            f"styles_applied={self._diag_styles_applied} styles_noop={self._diag_styles_noop} hmi_actions={self._diag_hmi_actions}"
        )
        self._diag_eval_total = 0
        self._diag_eval_matched = 0
        self._diag_styles_applied = 0
        self._diag_styles_noop = 0
        self._diag_hmi_actions = 0

        self._button.setFont(self.font)

    # This instrument is selectable
    def enc_selectable(self):
        return True

    # Highlight this instrument to show it is the current selection
    def enc_highlight(self,onoff):
        if onoff:
            self._style['bg_override'] = QColor('orange')
            fix.db.set_value('HIDEBUTTON', False) 
        else:
            self._style['bg_override'] = None 
        self.setStyle()
        # Change the bg color to the value passed in color
        # Will save old color so it can be returned to normal

    # Trigger a press of this button
    def enc_select(self):
        if self._toggle:
            self._button.setChecked(not self._button.isChecked())
        else:
            self.processConditions(clicked=True)
        # Will trigger as if the button was selected
        # Will return control back to the caller
        return False 
