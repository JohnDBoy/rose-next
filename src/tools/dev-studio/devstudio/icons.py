"""Line icons, drawn on a 24-unit grid and tinted at render time.

One stroke weight, round caps and joins, no fills (except the logo): a set
drawn to one rule looks like a set, which mixed icon packs never do. They are
rendered through QSvgRenderer at the screen's device pixel ratio, so they stay
crisp at 125-200% scaling. ``icon_file`` writes a tinted copy to disk for the
few places Qt only takes an image by URL (stylesheet arrows).
"""
import os
import tempfile

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from . import theme

PATHS = {
    "files": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 9.5h18M3 14.75h18M9 9.5V20"/>',
    "text": '<path d="M5 7.5V5h14v2.5M12 5v14M9 19h6"/>',
    "folder": '<path d="M3.5 7A2 2 0 0 1 5.5 5h3.6l2 2.2h7.4a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "save": '<path d="M5 3.5h10.5l5 5V19a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19V5A1.5 1.5 0 0 1 5 3.5z"/><path d="M7.5 3.5v4.5h7V3.5M7.5 20.5v-6h9v6"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12.5A1.5 1.5 0 0 0 8.5 21h7a1.5 1.5 0 0 0 1.5-1.5L18 7M9 7V4h6v3"/>',
    "eraser": '<path d="M8 20 3.7 15.7a1.5 1.5 0 0 1 0-2.1l9.4-9.4a1.5 1.5 0 0 1 2.1 0l4.6 4.6a1.5 1.5 0 0 1 0 2.1L11 20z"/><path d="M8 20h12M8.5 9.5l6 6"/>',
    "filter": '<path d="M3.5 5h17l-6.5 7.5V19l-4 2v-8.5z"/>',
    "x": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "chevron-right": '<path d="m9.5 6 6 6-6 6"/>',
    "chevron-down": '<path d="m6 9.5 6 6 6-6"/>',
    "chevron-up": '<path d="m6 14.5 6-6 6 6"/>',
    "command": '<path d="M9 6.5A2.5 2.5 0 1 0 6.5 9H17.5A2.5 2.5 0 1 0 15 6.5v11a2.5 2.5 0 1 0 2.5-2.5h-11A2.5 2.5 0 1 0 9 17.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M2.5 12h2M19.5 12h2M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "panel-right": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M15 4v16"/>',
    "external": '<path d="M7 17 17 7M9 7h8v8"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.6-4.5M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5M20 20v-4h-4"/>',
    "eye-off": '<path d="M3 3l18 18M10.6 6.1A9.6 9.6 0 0 1 12 6c5 0 9 6 9 6a15.6 15.6 0 0 1-2.5 3.1M6.6 6.7C4.3 8.2 3 12 3 12s4 6 9 6a8.9 8.9 0 0 0 4.3-1.1M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "hash": '<path d="M5 9h14M5 15h14M10.5 4 8.5 20M15.5 4l-2 16"/>',
    "alert": '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.2v.1"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8v.1"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "rows-plus": '<path d="M4 6h16M4 12h9M4 18h9M18 14v8M14 18h8"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
    "clipboard": '<rect x="5" y="4.5" width="14" height="16.5" rx="2"/><path d="M9 4.5V3h6v1.5M9 11h6M9 15h4"/>',
    "sort": '<path d="M7 4v16M3.5 16.5 7 20l3.5-3.5M17 20V4M13.5 7.5 17 4l3.5 3.5"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "dot": '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
    "swords": '<path d="M14.5 17.5 3.5 6.5V3.5h3l11 11M13 19l6-6M16 16l4 4M19 21l2-2"/>'
              '<path d="M14.5 6.5 17.5 3.5h3v3l-3 3M5 14l4 4M7 17l-3 3M3 19l2 2"/>',
}

LOGO = ('<path d="M12 21.5v-6.5" stroke-width="1.8"/>'
        '<path d="M12 15c-4.6 0-7-3.4-7-7.2 2.6.2 5 1.4 7 3.6 2-2.2 4.4-3.4 7-3.6 0 3.8-2.4 7.2-7 7.2z" fill="currentColor" stroke="none"/>'
        '<path d="M12 11.6C10.1 9.6 10 6.4 12 3.5c2 2.9 1.9 6.1 0 8.1z" fill="currentColor" stroke="none" opacity=".7"/>'
        '<path d="M12 18.5c1.6-1.6 3.6-2.2 5.6-1.8-.8 1.9-3 3-5.6 1.8z" fill="currentColor" stroke="none" opacity=".55"/>')

_cache = {}
_files = {}


def _svg(name, color, stroke=1.75):
    body = LOGO if name == "logo" else PATHS[name]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            'stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" '
            'color="%s">%s</svg>' % (color, stroke, color, body.replace("currentColor", color)))


def pixmap(name, color=None, size=16, stroke=1.75):
    color = color or theme.current().text_dim
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    key = (name, color, size, stroke, dpr)
    pm = _cache.get(key)
    if pm is None:
        r = QSvgRenderer(QByteArray(_svg(name, color, stroke).encode()))
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r.render(p, QRectF(0, 0, size * dpr, size * dpr))
        p.end()
        pm.setDevicePixelRatio(dpr)
        _cache[key] = pm
    return pm


def icon(name, color=None, size=16, active=None):
    """A QIcon tinted ``color``; ``active`` (default: the text colour) is used
    while hovered or checked, which is what makes a toolbar feel alive."""
    t = theme.current()
    ic = QIcon()
    normal = pixmap(name, color or t.text_dim, size)
    on = pixmap(name, active or t.text, size)
    ic.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(on, QIcon.Mode.Active, QIcon.State.Off)
    ic.addPixmap(on, QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(on, QIcon.Mode.Active, QIcon.State.On)
    ic.addPixmap(pixmap(name, t.text_faint, size), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


def icon_file(name, color):
    key = (name, color)
    if key not in _files:
        d = os.path.join(tempfile.gettempdir(), "rose-dev-studio-icons")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "%s-%s.svg" % (name, color.strip("#")))
        with open(path, "w", encoding="ascii") as fh:
            fh.write(_svg(name, color))
        _files[key] = path
    return _files[key]


def clear_cache():
    _cache.clear()
