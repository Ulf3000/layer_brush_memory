"""
layer_brush_memory — stores brush state and/or tool state per layer.

Two independent flags per layer uid:
  tool_excluded  — uid in self._tool_excluded  → tool memory off for that layer
  brush_excluded — uid in self._brush_excluded → brush memory off for that layer

Stored data per uid (self._data[uid]):
  'tool'  — objectName of the checked ToolBox button
  'n','s','o','f','b','fg','bg' — brush state (paint-capable layers only)

On layer switch:
  1. capture tool (always) + brush (if paint-capable) → store under prev uid
  2. 80ms later: restore tool (if not tool_excluded) then brush (if not brush_excluded)

First visit (no stored data): apply _DEFAULT_TOOL_BY_TYPE if tool memory is on.
"""

import json
import os

from krita import Krita, Extension
from PyQt5.QtCore    import QByteArray, QObject, QTimer, QEvent, Qt
from PyQt5.QtGui     import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtSvg     import QSvgRenderer
from PyQt5.QtWidgets import (
    QApplication, QMenu, QAction,
    QToolButton, QDoubleSpinBox, QTreeView,
    QButtonGroup,
)

from .layer_brush_plugin import PLUGIN_NAME

_app        = Krita.instance()
_PLUGIN_DIR = os.path.dirname(__file__)

DEFAULT_TOOL_ON   = True
DEFAULT_BRUSH_ON  = True

_BRUSH_ELIGIBLE_TYPES = {'paintlayer', 'transparencymask', 'selectionmask', 'filtermask'}

_DEFAULT_TOOL_BY_TYPE: dict[str, str] = {
    'vectorlayer':      'SvgTextTool',
    'paintlayer':       'KritaShape/KisToolBrush',
    'transparencymask': 'KritaShape/KisToolBrush',
    'selectionmask':    'KritaShape/KisToolBrush',
    'filtermask':       'KritaShape/KisToolBrush',
    'grouplayer':       'KritaShape/KisToolTransform',
    'clonelayer':       'KritaShape/KisToolTransform',
}


# ---------------------------------------------------------------------------
# Icons  (two independent icon pairs: tool / brush)
# ---------------------------------------------------------------------------

_ICONS: dict[str, QIcon] = {}

def _icon(kind: str, on: bool) -> QIcon:
    """kind = 'tool' | 'brush'"""
    key = f'{kind}_{on}'
    if key not in _ICONS:
        base = QPixmap(16, 16)
        base.fill(Qt.transparent)
        svg = os.path.join(_PLUGIN_DIR, 'paint.svg' if kind == 'brush' else 'tool.svg')
        if os.path.exists(svg):
            r = QSvgRenderer(svg)
            p = QPainter(base); r.render(p); p.end()
        if on:
            tinted = QPixmap(base.size())
            tinted.fill(Qt.transparent)
            p = QPainter(tinted)
            p.drawPixmap(0, 0, base)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(tinted.rect(), QColor('#ed174b'))
            p.end()
            _ICONS[key] = QIcon(tinted)
        else:
            _ICONS[key] = QIcon(base)
    return _ICONS[key]


# ---------------------------------------------------------------------------
# Safe accessors
# ---------------------------------------------------------------------------

def _view():
    try:
        w = _app.activeWindow()
        if w is None: return None
        v = w.activeView()
        if v is None: return None
        v.document()
        return v
    except Exception:
        return None

def _node():
    try:
        w = _app.activeWindow()
        if w is None: return None
        v = w.activeView()
        if v is None: return None
        d = v.document()
        if d is None: return None
        n = d.activeNode()
        if n is None: return None
        n.name()
        return n
    except Exception:
        return None

def _uid(node):
    try:
        return node.uniqueId().toString(False)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ToolBox access
# ---------------------------------------------------------------------------

def _toolbox_bg() -> QButtonGroup | None:
    try:
        dock = next((w for w in _app.dockers() if w.objectName() == 'ToolBox'), None)
        if dock is None: return None
        return dock.findChild(QButtonGroup)
    except Exception:
        return None

def _capture_tool() -> str | None:
    try:
        bg = _toolbox_bg()
        if bg is None: return None
        btn = bg.checkedButton()
        return btn.objectName() if btn else None
    except Exception:
        return None

def _restore_tool(tool_id: str) -> None:
    try:
        bg = _toolbox_bg()
        if bg is None: return
        for btn in bg.buttons():
            if btn.objectName() == tool_id:
                btn.click()
                return
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Capture / restore
# ---------------------------------------------------------------------------

def _capture(view, node_type: str | None) -> dict:
    """Always returns a dict (may be empty). Caller decides what to store."""
    entry: dict = {}
    try:
        tool_id = _capture_tool()
        if tool_id:
            entry['tool'] = tool_id
    except Exception: pass
    if node_type is None or node_type in _BRUSH_ELIGIBLE_TYPES:
        try:
            preset = view.currentBrushPreset()
            if preset is not None:
                entry.update({
                    'n':  preset.name(),
                    's':  view.brushSize(),
                    'o':  view.paintingOpacity(),
                    'f':  view.paintingFlow(),
                    'b':  view.currentBlendingMode(),
                    'fg': list(view.foregroundColor().components()),
                    'bg': list(view.backgroundColor().components()),
                })
        except Exception: pass
    return entry

def _restore(view, data: dict, restore_tool: bool, restore_brush: bool,
             node_type: str | None = None) -> None:
    if restore_tool:
        tool = data.get('tool')
        if tool:
            _restore_tool(tool)
        else:
            # first-visit default
            default = _DEFAULT_TOOL_BY_TYPE.get(node_type or '')
            if default:
                _restore_tool(default)

    if restore_brush and (node_type is None or node_type in _BRUSH_ELIGIBLE_TYPES):
        try:
            p = _app.resources('preset').get(data.get('n', ''))
            if p: view.setCurrentBrushPreset(p)
        except Exception: pass
        try: view.setBrushSize(data['s'])
        except Exception: pass
        try: view.setPaintingOpacity(data['o'])
        except Exception: pass
        try: view.setPaintingFlow(data['f'])
        except Exception: pass
        try: view.setCurrentBlendingMode(data['b'])
        except Exception: pass
        try:
            fg = view.foregroundColor()
            fg.setComponents(data['fg'])
            view.setForeGroundColor(fg)
        except Exception: pass
        try:
            bg = view.backgroundColor()
            bg.setComponents(data['bg'])
            view.setBackGroundColor(bg)
        except Exception: pass


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class _Handler(QObject):

    def __init__(self, action_tool, action_brush):
        super().__init__()
        self._action_tool  = action_tool
        self._action_brush = action_brush

        self._list_layers  = None
        self._ctx_filter   = None

        # Two button slots per injection point (opacity row + toolbar row)
        # Each slot holds (tool_btn, brush_btn) or (None, None)
        self._opacity_btns: tuple[QToolButton | None, QToolButton | None] = (None, None)
        self._toolbar_btns: tuple[QToolButton | None, QToolButton | None] = (None, None)

        # Per-uid state
        self._data:           dict[str, dict] = {}   # uid → captured data
        self._tool_excluded:  set[str]        = set()
        self._brush_excluded: set[str]        = set()

        # Previous layer state (captured at selection time)
        self._prev_uid:       str | None = None
        self._prev_eligible:  bool       = False
        self._prev_node_type: str | None = None

        try:
            n = _app.notifier()
            n.setActive(True)
            n.viewCreated.connect(lambda *a: QTimer.singleShot(500, self._on_ready))
            n.imageCreated.connect(lambda *a: QTimer.singleShot(500, self._on_ready))
            n.imageSaved.connect(self._on_image_saved)
        except Exception:
            pass

        self._flush_timer = QTimer(interval=10000, timeout=self._flush_to_doc)
        self._flush_timer.start()

        QTimer.singleShot(300, self._connect_layer_menu)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _tool_on(self, uid: str | None) -> bool:
        return (uid not in self._tool_excluded) if uid else DEFAULT_TOOL_ON

    def _brush_on(self, uid: str | None) -> bool:
        return (uid not in self._brush_excluded) if uid else DEFAULT_BRUSH_ON

    # -----------------------------------------------------------------------
    # Ready / wiring
    # -----------------------------------------------------------------------

    def _on_ready(self):
        if _view() is None:
            QTimer.singleShot(500, self._on_ready)
            return
        self._load_from_doc()
        self._wire_layer_box()
        n = _node()
        if n:
            self._prev_uid       = _uid(n)
            self._prev_eligible  = True
            self._prev_node_type = n.type()

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def _flush_to_doc(self):
        try:
            w = _app.activeWindow()
            if not w: return
            doc = w.activeView().document()
            if not doc: return
            payload = {
                'data':          self._data,
                'tool_excluded': list(self._tool_excluded),
                'brush_excluded':list(self._brush_excluded),
            }
            raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            doc.setAnnotation(PLUGIN_NAME, 'layer brush memory', QByteArray(raw))
        except Exception:
            pass

    def _load_from_doc(self):
        try:
            w = _app.activeWindow()
            if not w: return
            doc = w.activeView().document()
            if not doc: return
            if PLUGIN_NAME not in doc.annotationTypes(): return
            payload = json.loads(bytes(doc.annotation(PLUGIN_NAME)).decode('utf-8'))
            # support old format that used 'brushes'/'excluded' keys
            self._data           = payload.get('data', payload.get('brushes', {}))
            self._tool_excluded  = set(payload.get('tool_excluded', payload.get('excluded', [])))
            self._brush_excluded = set(payload.get('brush_excluded', []))
        except Exception:
            pass

    def _on_image_saved(self, *args):
        self._flush_to_doc()

    # -----------------------------------------------------------------------
    # Layer switch
    # -----------------------------------------------------------------------

    def _on_current_changed(self, current_index, previous_index):
        v = _view()
        if v and self._prev_uid and self._prev_eligible:
            data = _capture(v, self._prev_node_type)
            if data:
                self._data[self._prev_uid] = data
        QTimer.singleShot(80, self._restore_current)

    def _restore_current(self):
        v = _view()
        n = _node()
        if v is None or n is None: return
        uid = _uid(n)
        if uid is None: return

        self._prev_uid       = uid
        self._prev_eligible  = True
        self._prev_node_type = n.type()

        do_tool  = self._tool_on(uid)
        do_brush = self._brush_on(uid)

        if do_tool or do_brush:
            data = self._data.get(uid, {})
            _restore(v, data,
                     restore_tool=do_tool,
                     restore_brush=do_brush,
                     node_type=n.type())

        self._refresh_ui()

    # -----------------------------------------------------------------------
    # Toggles
    # -----------------------------------------------------------------------

    def toggle_tool(self):
        uid = _uid(_node())
        if uid is None: return
        if uid in self._tool_excluded:
            self._tool_excluded.discard(uid)
        else:
            self._tool_excluded.add(uid)
        self._refresh_ui()

    def toggle_brush(self):
        uid = _uid(_node())
        if uid is None: return
        if uid in self._brush_excluded:
            self._brush_excluded.discard(uid)
        else:
            self._brush_excluded.add(uid)
        self._refresh_ui()

    # -----------------------------------------------------------------------
    # UI refresh
    # -----------------------------------------------------------------------

    def _refresh_ui(self):
        n   = _node()
        uid = _uid(n) if n else None
        node_type = n.type() if n else None

        tool_eligible  = True  # all types
        brush_eligible = node_type in _BRUSH_ELIGIBLE_TYPES if node_type else False

        tool_on  = tool_eligible  and self._tool_on(uid)
        brush_on = brush_eligible and self._brush_on(uid)

        # Menu actions
        try: self._action_tool.setChecked(tool_on);   self._action_tool.setEnabled(tool_eligible)
        except Exception: pass
        try: self._action_brush.setChecked(brush_on); self._action_brush.setEnabled(brush_eligible)
        except Exception: pass

        # Button pairs
        tb, bb = self._opacity_btns
        self._update_btn(tb, tool_on,  tool_eligible,  'tool')
        self._update_btn(bb, brush_on, brush_eligible, 'brush')
        tb, bb = self._toolbar_btns
        self._update_btn(tb, tool_on,  tool_eligible,  'tool')
        self._update_btn(bb, brush_on, brush_eligible, 'brush')

    def _update_btn(self, btn, on, enabled, kind):
        if btn is None: return
        try:
            btn.setEnabled(enabled)
            btn.setChecked(on)
            btn.setIcon(_icon(kind, on))
        except Exception: pass

    # -----------------------------------------------------------------------
    # Layer menu
    # -----------------------------------------------------------------------

    def _connect_layer_menu(self):
        try:
            window = _app.activeWindow()
            if not window:
                QTimer.singleShot(500, self._connect_layer_menu)
                return
            qwin = window.qwindow()
            if not qwin: return
            for action in qwin.menuBar().actions():
                if action.objectName() == 'layer' or \
                   action.text().replace('&', '') == 'Layer':
                    m = action.menu()
                    if m: m.aboutToShow.connect(self._refresh_ui)
                    return
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # KisLayerBox wiring
    # -----------------------------------------------------------------------

    def _wire_layer_box(self):
        try:
            window = _app.activeWindow()
            if not window: return
            klb = next((d for d in window.dockers()
                        if d.objectName() == 'KisLayerBox'), None)
            if not klb:
                QTimer.singleShot(500, self._wire_layer_box)
                return
            tree = klb.findChild(QTreeView, 'listLayers')
            if not tree: return

            if self._list_layers is not None and self._list_layers is not tree:
                try:
                    self._list_layers.selectionModel().currentChanged.disconnect(
                        self._on_current_changed)
                except Exception: pass

            self._list_layers = tree
            tree.selectionModel().currentChanged.connect(self._on_current_changed)

            if self._ctx_filter:
                tree.removeEventFilter(self._ctx_filter)
            self._ctx_filter = _CtxFilter(tree, self)
            tree.installEventFilter(self._ctx_filter)

            self._inject_opacity_btns(klb)
            self._inject_toolbar_btns(klb)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Button injection
    # -----------------------------------------------------------------------

    def _make_btn(self, parent, w, h, kind, toggle_fn):
        btn = QToolButton(parent)
        btn.setCheckable(True)
        btn.setFixedSize(w, h)
        btn.setToolTip(f'Remember {kind} for this layer')
        btn.setIcon(_icon(kind, True))
        btn.clicked.connect(toggle_fn)
        return btn

    def _inject_opacity_btns(self, klb):
        if self._opacity_btns != (None, None): return
        try:
            spin = klb.findChild(QDoubleSpinBox, 'doubleOpacity')
            if not spin: return
            row    = spin.parent()
            layout = row.layout() if row else None
            if not layout: return
            idx = next((i for i in range(layout.count())
                        if layout.itemAt(i) and layout.itemAt(i).widget() is spin), -1)
            if idx == -1: return
            tb = self._make_btn(row, 22, 22, 'tool',  self.toggle_tool)
            bb = self._make_btn(row, 22, 22, 'brush', self.toggle_brush)
            layout.insertWidget(idx + 1, tb)
            layout.insertWidget(idx + 2, bb)
            self._opacity_btns = (tb, bb)
            self._refresh_ui()
        except Exception: pass

    def _inject_toolbar_btns(self, klb):
        if self._toolbar_btns != (None, None): return
        try:
            delete_btn = klb.findChild(QToolButton, 'bnDelete')
            if not delete_btn: return
            shared = delete_btn.parent()
            vbox   = shared.layout() if shared else None
            if not vbox: return
            toolbar_widget = layout = None
            for i in range(vbox.count()):
                vitem   = vbox.itemAt(i)
                child_w = vitem.widget()  if vitem else None
                child_l = vitem.layout()  if vitem else None
                tlay    = child_w.layout() if child_w else child_l
                tw      = child_w          if child_w else shared
                if tlay:
                    for j in range(tlay.count()):
                        it = tlay.itemAt(j)
                        if it and it.widget() is delete_btn:
                            toolbar_widget, layout = tw, tlay
                            break
                if toolbar_widget: break
            if not toolbar_widget or not layout: return
            idx = next((i for i in range(layout.count())
                        if layout.itemAt(i) and layout.itemAt(i).widget() is delete_btn), -1)
            if idx == -1: return
            tb = self._make_btn(toolbar_widget, 30, 29, 'tool',  self.toggle_tool)
            bb = self._make_btn(toolbar_widget, 30, 29, 'brush', self.toggle_brush)
            layout.insertWidget(idx,     tb)
            layout.insertWidget(idx + 1, bb)
            tb.show(); bb.show()
            self._toolbar_btns = (tb, bb)
            self._refresh_ui()
        except Exception: pass


# ---------------------------------------------------------------------------
# Context menu
# ---------------------------------------------------------------------------

class _CtxFilter(QObject):
    def __init__(self, tree, handler):
        super().__init__(tree)
        self._handler = handler

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ContextMenu:
            QTimer.singleShot(0, self._inject)
        return False

    def _inject(self):
        try:
            menu = QApplication.activePopupWidget()
            if not isinstance(menu, QMenu): return
            n = _node()
            if n is None: return
            uid       = _uid(n)
            h         = self._handler
            tool_on   = h._tool_on(uid)
            brush_on  = h._brush_on(uid)

            act_tool = QAction(
                ('Disable' if tool_on else 'Enable') + ' tool memory for this layer', menu)
            act_tool.setIcon(_icon('tool', not tool_on))
            act_tool.triggered.connect(h.toggle_tool)

            act_brush = QAction(
                ('Disable' if brush_on else 'Enable') + ' brush memory for this layer', menu)
            act_brush.setIcon(_icon('brush', not brush_on))
            act_brush.triggered.connect(h.toggle_brush)

            first = menu.actions()[0] if menu.actions() else None
            menu.insertAction(first, act_brush)
            menu.insertAction(first, act_tool)
            menu.insertSeparator(first)
        except Exception: pass


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

class LayerBrushExtension(Extension):

    @classmethod
    def register(cls):
        ext = cls(_app)
        ext.setObjectName(f'{PLUGIN_NAME}:extension')
        _app.addExtension(ext)

    def setup(self):
        self._handler = None

    def createActions(self, window):
        act_tool = window.createAction(
            f'{PLUGIN_NAME}:toggle_tool',
            'Remember Tool for this Layer',
            'layer')
        act_tool.setCheckable(True)
        act_tool.setChecked(DEFAULT_TOOL_ON)
        act_tool.setIcon(_icon('tool', DEFAULT_TOOL_ON))

        act_brush = window.createAction(
            f'{PLUGIN_NAME}:toggle_brush',
            'Remember Brush for this Layer',
            'layer')
        act_brush.setCheckable(True)
        act_brush.setChecked(DEFAULT_BRUSH_ON)
        act_brush.setIcon(_icon('brush', DEFAULT_BRUSH_ON))

        if self._handler is None:
            self._handler = _Handler(act_tool, act_brush)

        act_tool.triggered.connect(self._handler.toggle_tool)
        act_brush.triggered.connect(self._handler.toggle_brush)