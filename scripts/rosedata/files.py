"""File helpers the importers share: data-relative paths, copying, asset chains.

Data-relative paths are the backslash form the game tables hold
(``3DDATA\\NPC\\...``); ``rel_path`` turns one into a real path under a data
root. ``copy_files`` copies what a dump has and we lack, never overwriting.
``effect_chain`` walks ``.eft -> .PTL -> particle texture`` by pattern: both
are length-prefixed binary and the paths are all that is needed, so a full
parser would be more code for the same answer; a ``.PTL`` names its textures
bare, so those resolve against the shared particle texture directory.
"""
import os
import shutil

from rosefmt.stb import backup  # noqa: F401  (the one-time .bak beside a file)

from .schema import ABS_ASSET_RE, BARE_TEXTURE_RE, PARTICLE_TEXTURE_DIR


def norm(p):
    """A path as a case- and separator-insensitive key."""
    if isinstance(p, bytes):
        p = p.decode("latin-1")
    return p.replace("\\", "/").lower()


def rel_path(root, rel):
    return os.path.join(root, rel.replace("\\", "/"))


def copy_files(rels, src_root, dst_root, dry, label):
    """Copy data-relative paths that we do not already have. Returns (n, bytes)."""
    n, total, missing = 0, 0, []
    for rel in sorted(set(rels)):
        s = rel_path(src_root, rel)
        d = rel_path(dst_root, rel)
        if not os.path.isfile(s):
            missing.append(rel)
            continue
        if os.path.isfile(d):
            continue
        n += 1
        total += os.path.getsize(s)
        if not dry:
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d)
    print(f"    {label:26s} {n:5d} new files  {total / 1048576:7.2f} MB"
          + (f"   ({len(missing)} not in source)" if missing else ""))
    for m in missing[:5]:
        print(f"        missing from source: {m}")
    return n, total


def effect_chain(efts, src):
    """.eft -> .PTL -> particle texture, transitively (data-relative paths)."""
    out, queue, seen = set(), list(efts), set()
    while queue:
        rel = queue.pop()
        if rel.lower() in seen:
            continue
        seen.add(rel.lower())
        out.add(rel)
        p = rel_path(src, rel)
        if not os.path.isfile(p):
            continue
        blob = open(p, "rb").read()
        for hit in ABS_ASSET_RE.finditer(blob):
            queue.append(hit.group().decode("latin-1"))
        if rel.lower().endswith(".ptl"):
            for hit in BARE_TEXTURE_RE.finditer(blob):
                queue.append(os.path.join(PARTICLE_TEXTURE_DIR,
                                          hit.group().decode("latin-1")))
    return out


def find_asset(base, name):
    """Find a file by basename anywhere under a data root (dumps are case-mixed)."""
    want = os.path.basename(name).lower()
    for r, _, fs in os.walk(base):
        for f in fs:
            if f.lower() == want:
                return os.path.join(r, f)
    return None


def find_qsd(base, name):
    root = os.path.join(base, "3DDATA", "QUESTDATA")
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.lower() == name.lower():
                return os.path.join(r, f)
    return None
