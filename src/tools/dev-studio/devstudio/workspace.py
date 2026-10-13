"""The data folder: which files exist, and how tables and string files pair up.

``LIST_WEAPON.STB`` names its rows through ``LIST_WEAPON_S.STL``: one STB column
holds the STL key (``LWEA001``). Which column varies by table and by dump (45 on
our LIST_WEAPON, the last column on Jrose's), so it is found by matching cells
against the STL's actual keys rather than hardcoded -- the wrong guess would
show wrong names, not an error.
"""
import os
import struct

from rosefmt import Stb, Stl

KINDS = {".stb": "stb", ".stl": "stl"}
SKIP_DIRS = {"content", "estb_backup", "__pycache__", ".git"}


def find_ci(folder, name):
    """Case-insensitive lookup of ``name`` in ``folder`` (the data mixes cases)."""
    try:
        for f in os.listdir(folder):
            if f.lower() == name.lower():
                return os.path.join(folder, f)
    except OSError:
        pass
    return None


def companion_stl(stb_path):
    folder, base = os.path.split(stb_path)
    stem = os.path.splitext(base)[0]
    return find_ci(folder, stem + "_S.STL")


def companion_stb(stl_path):
    folder, base = os.path.split(stl_path)
    stem = os.path.splitext(base)[0]
    if stem.upper().endswith("_S"):
        return find_ci(folder, stem[:-2] + ".STB")
    return None


def peek(path):
    """Cheap one-line description from the header alone."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(512)
    except OSError:
        return ""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".stb" and head[:4] == b"STB1":
            _, rows, cols = struct.unpack_from("<III", head, 4)
            return "%s × %d" % (format(rows - 1, ","), cols - 1)
        if ext == ".stl":
            n = head[0]
            tag = head[1:1 + n]
            count, = struct.unpack_from("<I", head, 1 + n)
            return "%s · %s" % (format(count, ","), tag.decode("latin-1"))
    except struct.error:
        pass
    return ""


def sniff_key_column(stb_rows, keys):
    """The STB column whose cells are STL keys: most hits on a sample of rows."""
    if not keys:
        return None
    sample = [row for row in stb_rows if any(x.strip() for x in row)][:500]
    if not sample:
        return None
    best, best_hits = None, 0
    for c in range(len(sample[0])):
        hits = sum(1 for row in sample if c < len(row) and row[c].strip() in keys)
        if hits > best_hits:
            best, best_hits = c, hits
    filled = len(sample)
    return best if best_hits >= max(3, 0.3 * filled) else None


class Workspace:
    def __init__(self, root):
        self.root = os.path.normpath(os.path.abspath(root))
        self.files = []        # (kind, abs path, rel path)
        self._names = {}       # stl path -> (stamp, {key: name})
        self._stb_cache = {}   # stb path -> (stamp, Stb) for reverse lookups

    def scan(self):
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for f in filenames:
                kind = KINDS.get(os.path.splitext(f)[1].lower())
                if kind and not f.startswith("."):
                    p = os.path.join(dirpath, f)
                    out.append((kind, p, os.path.relpath(p, self.root)))
        out.sort(key=lambda t: (t[0], os.path.basename(t[1]).lower(), t[2].lower()))
        self.files = out
        return out

    def rel(self, path):
        try:
            return os.path.relpath(path, self.root)
        except ValueError:
            return path

    @staticmethod
    def _stamp(path):
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def names_for(self, stl_path, open_doc=None):
        """{key bytes: display name}. Taken live from an open document, else
        read from disk (cached until the file changes)."""
        if open_doc is not None:
            return {k.encode("latin-1") if isinstance(k, str) else k: v
                    for k, v in open_doc.names_by_key().items()}
        stamp = self._stamp(stl_path)
        hit = self._names.get(stl_path)
        if hit and hit[0] == stamp:
            return hit[1]
        from .documents import StlDocument
        try:
            names = StlDocument(stl_path).names_by_key()
        except Exception:
            names = {}
        self._names[stl_path] = (stamp, names)
        return names

    def stb_rows_with_key(self, stb_path, key, open_doc=None):
        """Rows of ``stb_path`` whose key column holds ``key`` (STL -> STB links)."""
        kb = key.encode("latin-1")
        if open_doc is not None:
            rows, kc = open_doc.stb.d, open_doc.key_col
        else:
            stamp = self._stamp(stb_path)
            hit = self._stb_cache.get(stb_path)
            if not hit or hit[0] != stamp:
                try:
                    hit = (stamp, Stb(stb_path))
                except Exception:
                    return []
                self._stb_cache[stb_path] = hit
            stb = hit[1]
            rows = stb.d
            stl = companion_stl(stb_path)
            keys = set(self.names_for(stl)) if stl else set()
            kc = sniff_key_column(rows, keys)
        if kc is None:
            return []
        return [r for r, row in enumerate(rows) if kc < len(row) and row[kc].strip() == kb]
