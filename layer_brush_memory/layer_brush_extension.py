"""
layer_brush_memory — stores brush state in a plain Python dict.
No polling. No node writes. No annotation writes.
On layer switch: save current brush to the OLD node's UUID, restore from NEW node's UUID.
UUID is read once while the node is known-safe (at selection time).
"""

import json
import os

from krita import Krita, Extension
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore    import QObject, QTimer, QEvent, Qt
from PyQt5.QtGui     import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtSvg     import QSvgRenderer
from PyQt5.QtWidgets import (
    QApplication, QMenu, QAction,
    QToolButton, QDoubleSpinBox, QTreeView,
)

from .layer_brush_plugin import PLUGIN_NAME

_app       = Krita.instance()
_PLUGIN_DIR = os.path.dirname(__file__)

DEFAULT_REMEMBERED = True   # False = opt-in

# Node types that participate in brush memory.
# Add more type strings here to extend coverage.
_ELIGIBLE_TYPES = {'paintlayer', 'transparencymask', 'selectionmask', 'filtermask'}


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

_ICON_ON = _ICON_OFF = None

def _icon(on):
    global _ICON_ON, _ICON_OFF
    if _ICON_ON is None:
        base = QPixmap(16, 16)
        base.fill(Qt.transparent)
        path = os.path.join(_PLUGIN_DIR, 'icon_off.svg')
        if os.path.exists(path):
            r = QSvgRenderer(path)
            p = QPainter(base); r.render(p); p.end()
        tinted = QPixmap(base.size())
        tinted.fill(Qt.transparent)
        p = QPainter(tinted)
        p.drawPixmap(0, 0, base)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(tinted.rect(), QColor('#ed174b'))
        p.end()
        _ICON_ON  = QIcon(tinted)
        _ICON_OFF = QIcon(base)
    return _ICON_ON if on else _ICON_OFF


# ---------------------------------------------------------------------------
# Safe accessors
# ---------------------------------------------------------------------------

def _view():
    try:
        w = _app.activeWindow()
        if w is None: return None
        v = w.activeView()
        if v is None: return None
        v.document()  # poke
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
        n.name()  # poke
        return n
    except Exception:
        return None

def _uid(node):
    try:
        return node.uniqueId().toString(False)
    except Exception:
        return None

def _is_eligible(node):
    """Return True only for node types that participate in brush memory."""
    try:
        return node.type() in _ELIGIBLE_TYPES
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Brush capture / restore
# ---------------------------------------------------------------------------

def _capture(view):
    try:
        preset = view.currentBrushPreset()
        if preset is None: return None
        return {
            'n':  preset.name(),
            's':  view.brushSize(),
            'o':  view.paintingOpacity(),
            'f':  view.paintingFlow(),
            'b':  view.currentBlendingMode(),
            'fg': list(view.foregroundColor().components()),
            'bg': list(view.backgroundColor().components()),
        }
    except Exception:
        return None

def _restore(view, data):
    try:
        p = _app.resources('preset').get(data['n'])
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

    def __init__(self, menu_action):
        super().__init__()
        self._menu_action  = menu_action
        self._list_layers  = None
        self._ctx_filter   = None
        self._opacity_btn  = None
        self._toolbar_btn  = None

        # In-memory store: uid -> brush dict
        self._brushes: dict[str, dict] = {}
        # In-memory excluded set: uid strings
        self._excluded: set[str] = set()

        # uid and eligibility of the layer that was active when currentChanged fired.
        # Captured immediately while the old node is still safe.
        self._prev_uid: str | None = None
        self._prev_eligible: bool = False

        try:
            n = _app.notifier()
            n.setActive(True)
            n.viewCreated.connect(lambda *a: QTimer.singleShot(500, self._on_ready))
            n.imageCreated.connect(lambda *a: QTimer.singleShot(500, self._on_ready))
            # Flush on explicit save
            n.imageSaved.connect(self._on_image_saved)
        except Exception:
            pass

        # Also flush every 30s — catches autosave and crash recovery writes
        self._flush_timer = QTimer(interval=10000, timeout=self._flush_to_doc)
        self._flush_timer.start()

        QTimer.singleShot(300, self._connect_layer_menu)

    def _on_ready(self):
        if _view() is None:
            QTimer.singleShot(500, self._on_ready)
            return
        self._load_from_doc()
        self._wire_layer_box()
        # Seed prev_uid with whatever is active now
        n = _node()
        if n:
            self._prev_uid      = _uid(n)
            self._prev_eligible = _is_eligible(n)

    # -----------------------------------------------------------------------
    # Persistence — write/read full memory dict to document annotation
    # -----------------------------------------------------------------------

    def _flush_to_doc(self):
        """Write in-memory brush map to the active document annotation."""
        try:
            w = _app.activeWindow()
            if not w: return
            v = w.activeView()
            if not v: return
            doc = v.document()
            if not doc: return
            payload = {
                'brushes':  self._brushes,
                'excluded': list(self._excluded),
            }
            data = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            doc.setAnnotation(PLUGIN_NAME, 'layer brush memory', QByteArray(data))
        except Exception:
            pass

    def _load_from_doc(self):
        """Read brush map from document annotation into memory."""
        try:
            w = _app.activeWindow()
            if not w: return
            v = w.activeView()
            if not v: return
            doc = v.document()
            if not doc: return
            if PLUGIN_NAME not in doc.annotationTypes():
                return
            raw = bytes(doc.annotation(PLUGIN_NAME)).decode('utf-8')
            payload = json.loads(raw)
            self._brushes  = payload.get('brushes', {})
            self._excluded = set(payload.get('excluded', []))
        except Exception:
            pass

    def _on_image_saved(self, *args):
        self._flush_to_doc()

    # -----------------------------------------------------------------------
    # currentChanged — fired by the layer list selection model
    # Qt passes (current_index, previous_index) but we don't use them;
    # we use _prev_uid which we captured at the END of the last switch.
    # -----------------------------------------------------------------------

    def _on_current_changed(self, current_index, previous_index):
        # Step 1: save current brush to the PREVIOUS layer (still safe — view
        # hasn't changed yet, only the index moved)
        v = _view()
        if v and self._prev_uid and self._prev_eligible \
                and self._prev_uid not in self._excluded:
            data = _capture(v)
            if data:
                self._brushes[self._prev_uid] = data

        # Step 2: short delay then restore for the NEW layer
        QTimer.singleShot(80, self._restore_current)

    def _restore_current(self):
        v = _view()
        n = _node()
        if v is None or n is None:
            return

        uid = _uid(n)
        if uid is None:
            return

        # Remember this uid and eligibility as "previous" for the next switch
        self._prev_uid      = uid
        self._prev_eligible = _is_eligible(n)

        if self._prev_eligible and uid not in self._excluded:
            data = self._brushes.get(uid)
            if data:
                _restore(v, data)

        self._refresh_ui()

    # -----------------------------------------------------------------------
    # Toggle
    # -----------------------------------------------------------------------

    def do_toggle(self):
        n = _node()
        if n is None:
            return
        uid = _uid(n)
        if uid is None:
            return
        if uid in self._excluded:
            self._excluded.discard(uid)
        else:
            self._excluded.add(uid)
        self._refresh_ui()

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def _refresh_ui(self):
        n = _node()
        uid = _uid(n) if n else None
        eligible   = _is_eligible(n) if n else False
        remembered = eligible and ((uid not in self._excluded) if uid else DEFAULT_REMEMBERED)
        try: self._menu_action.setChecked(remembered)
        except Exception: pass
        try: self._menu_action.setEnabled(eligible)
        except Exception: pass
        for btn in (self._opacity_btn, self._toolbar_btn):
            try:
                if btn:
                    btn.setEnabled(eligible)
                    btn.setChecked(remembered)
                    btn.setIcon(_icon(remembered))
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

            self._inject_opacity_btn(klb)
            self._inject_toolbar_btn(klb)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Buttons
    # -----------------------------------------------------------------------

    def _inject_opacity_btn(self, klb):
        if self._opacity_btn: return
        try:
            spin = klb.findChild(QDoubleSpinBox, 'doubleOpacity')
            if not spin: return
            row = spin.parent()
            layout = row.layout() if row else None
            if not layout: return
            idx = next((i for i in range(layout.count())
                        if layout.itemAt(i) and layout.itemAt(i).widget() is spin), -1)
            if idx == -1: return
            btn = self._make_btn(row, 22, 22)
            self._opacity_btn = btn
            layout.insertWidget(idx + 1, btn)
            self._refresh_ui()
        except Exception: pass

    def _inject_toolbar_btn(self, klb):
        if self._toolbar_btn: return
        try:
            delete_btn = klb.findChild(QToolButton, 'bnDelete')
            if not delete_btn: return
            shared = delete_btn.parent()
            vbox = shared.layout() if shared else None
            if not vbox: return
            toolbar_widget = layout = None
            for i in range(vbox.count()):
                vitem = vbox.itemAt(i)
                child_w   = vitem.widget()             if vitem else None
                child_lay = vitem.layout()             if vitem else None
                tlay = child_w.layout() if child_w else child_lay
                tw   = child_w          if child_w else shared
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
            btn = self._make_btn(toolbar_widget, 30, 29)
            self._toolbar_btn = btn
            layout.insertWidget(idx, btn)
            btn.show()
            self._refresh_ui()
        except Exception: pass

    def _make_btn(self, parent, w, h):
        btn = QToolButton(parent)
        btn.setCheckable(True)
        btn.setFixedSize(w, h)
        btn.setToolTip('Remember brush for this layer (click to exclude)')
        btn.setIcon(_icon(DEFAULT_REMEMBERED))
        btn.clicked.connect(lambda: self.do_toggle())
        return btn


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
            uid = _uid(n)
            remembered = (uid not in self._handler._excluded) if uid else DEFAULT_REMEMBERED
            act = QAction(
                'Exclude from brush memory' if remembered else 'Remember brush for this layer',
                menu)
            act.setIcon(_icon(not remembered))
            act.triggered.connect(self._handler.do_toggle)
            first = menu.actions()[0] if menu.actions() else None
            menu.insertAction(first, act)
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
        action = window.createAction(
            f'{PLUGIN_NAME}:toggle',
            'Remember Brush for this Layer',
            'layer')
        action.setCheckable(True)
        action.setChecked(DEFAULT_REMEMBERED)
        action.setIcon(_icon(DEFAULT_REMEMBERED))

        if self._handler is None:
            self._handler = _Handler(action)

        action.triggered.connect(self._handler.do_toggle)