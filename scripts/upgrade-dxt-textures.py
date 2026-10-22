"""Swap DXT-compressed 3D textures for the uncompressed copies other clients ship.

Usage (from the repo root):
    python scripts/upgrade-dxt-textures.py --survey             # match, write review sheets (build/ only)
    python scripts/upgrade-dxt-textures.py --apply [--dry-run]  # write the surveyed plan
    python scripts/upgrade-dxt-textures.py --verify
    python scripts/upgrade-dxt-textures.py --restore

Why (2026-10-22): the original dump's 3D textures were blanket-converted to DXT,
like the icon sheets (upgrade-item-icons.py). A fresh texconv DXT5 of the clean
source scores the same as ours (33.4 vs 33.3 dB median), so re-encoding gains
nothing; only an uncompressed copy helps. At 256 px and up the block noise is
hard to see on a model, but a small texture stretched over a hat is another
matter: one 4x4 block covers a patch of the model (the user's Ranger Hat,
cap_01420.dds, 128 px, 25.7 dB against 668's copy). Imports since May came in
clean; only vanilla files are affected.

Matching is by path: a texture keeps its name across clients, unlike the icon
sheets. For every DXT texture of ours no larger than --max-size, the sources are
tried in order (SOURCES: 668, tsuki, Jrose) and the first usable copy wins:
  * uncompressed (16/24/32-bit) at the same dimensions;
  * not itself a decoded DXT image (some dumps store those as 24/32-bit): nearly
    every aligned 4x4 block then has at most four colours;
  * the same picture: the RMS of the 4x4 block means (the part DXT keeps) is at
    most MATCH_BLOCK, and no single block differs by more than WORST_BLOCK.
The Crystal set (lv220, career_a_009-012, any size) comes from Rose Brasil, the
look armour-ladder-pass.py gave it; that pass kept our DXT copies of the art.

Alpha: the copy's alpha is used (ROSE avatar textures keep a specular mask
there). A copy without alpha is taken only if ours is fully opaque. A pair whose
alpha differs (more than 1% of pixels by over 64) is "doubtful" and not applied
without --include-doubtful.

Output of --survey, build/texture-crisp-survey/ (nothing is written under data/):
  summary.txt   counts by verdict, source and folder; size cost
  plan.json     rel path -> source, verdict, metrics
  sheet-NN.png  ours (left) | copy (right), 2x, framed green (match) / orange
                (doubtful), for a look before --apply

--apply reads plan.json and writes each copy over ours at the same path and
size, as uncompressed 32-bit BGRA with MIPS levels (the engine caps every
texture at three, INIT.LUA setMipmapLevel(3)), the levels box-filtered like
add-dds-mipmaps.py's texconv runs. Cost: 4 bytes a pixel instead of 1 (DXT5).

Undo: every file is copied to build/texture-crisp/ (same relative path) before
its first write, recorded in its manifest; --restore copies them back. --verify
re-reads every written file: 32-bit uncompressed, legacy header, dimensions and
mip count, and mip 0 equal to its source.

Check: point the GM item browser at data/ (it reads loose files, no bake). Deploy
is client-only data: re-bake; no server restart.

RUNS ON RECORD (data/ is gitignored, so this list is the only committed history)
- 2026-10-22, --max-size 128 + Crystal: 624 textures (668 529, tsuki 41, Jrose 10,
  Brasil 44), 14.3 -> 56.1 MB (+41.8 MB). Matches sit at block distance <= 3.9,
  rejects at >= 34: nothing near the line. Rejected (different art in every
  client): 25 faces face1/face2_02500-04200 and 3 Junon object lightmaps. 71
  copies were decoded DXT and skipped. 256 px (543 files, ~+130 MB) left for later.
- 2026-10-22, --max-size 8192 (every size): 675 more (668 414, tsuki 257, Jrose 4),
  89.9 -> 353.4 MB (+263.6 MB); bake 2.94 GB. Left: 2 doubtful, 76 none. ~12,400
  DXT textures have no uncompressed copy in any client (~6,000 of them lightmaps).
- 2026-10-22, the 14 OVERRIDES after a review of the 78 leftovers (+12.0 MB); bake
  2.95 GB. Kept as they are, different art: 25 faces (668 redrew them), 15 lion
  fighter textures (tsuki recoloured), 3 repainted minimaps, ~16 lightmaps, 2 hairs,
  a poster, 2 weapons, a cart.
- 2026-10-22, --rewrite: the mips above were premultiplied (Pillow resizes RGBA that
  way), so armour whose alpha is a specular mask went black at distance in game
  (Ranger set; 896 of 1,313 off, 172 badly). All rebuilt per channel; cut-out
  textures (36) average colour over visible texels. --verify now checks every level.
- 2026-10-22, --fix-mips on the only two textures in data/ whose *shipped* chain was
  darker than mip 0 (a scan of all 13,644 chains): SW_PORTTREE004.DDS (DXT1 cut-out,
  leaves -25%) and u_dsw5_1.dds (-17%, premultiplied at import). Scan after: 0.
"""
import argparse, json, math, os, shutil, sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from rosefmt import dds  # noqa: E402

DATA = os.path.join("data", "3DDATA")
TESTCLIENTS = os.path.join(os.path.expanduser("~"), "Desktop", "Testclients")
SOURCES = [("668", os.path.join(TESTCLIENTS, "668", "Extracted", "3DDATA")),
           ("tsuki", os.path.join(TESTCLIENTS, "tsuki", "3DDATA")),
           ("jrose", os.path.join(TESTCLIENTS, "Jrose", "3DDATA"))]
CRYSTAL_SOURCE = ("brazil", os.path.join(TESTCLIENTS, "rose brazil", "Extracted", "3DDATA"))
CRYSTAL = ("career_a_009", "career_a_010", "career_a_011", "career_a_012")
OUT = os.path.join("build", "texture-crisp-survey")
BACKUP = os.path.join("build", "texture-crisp")
PLAN = os.path.join(OUT, "plan.json")
MANIFEST = os.path.join(BACKUP, "manifest.json")

MAX_SIZE = 128        # default: largest side; 256 px is a separate decision (+130 MB)
MIPS = 3
DXT_DECODED = 0.95    # share of 4x4 blocks with <= 4 colours that marks a decoded DXT copy
MATCH_BLOCK = 6.0     # set from the survey, see summary.txt
WORST_BLOCK = 60.0

# Rejected by the thresholds, accepted by eye (2026-10-22 review of the 78 leftovers).
#   take:       the copy as it is
#   keep-alpha: the copy's RGB with our alpha (the copy has none, ours carries a mask)
# The minimaps are the same painting with the place names relabelled to the names
# LIST_ZONE_S.STL already uses ("Beach of Genzi" -> "Kenji Beach", "Adventure Plane" ->
# "Adventurer's Plain"); 8x8-mean diffs show nothing else changed. NOT taken: JD01,
# JG02, JDT01, whose minimaps 668 repainted for terrain it reworked (heightmaps differ).
OVERRIDES = {
    "avatar\\body\\body1_00400.dds": "take",          # same art, worst block 62 vs 60
    "npc\\npc\\leprechaun\\body01.dds": "keep-alpha",
    "npc\\npc\\leprechaun\\head01.dds": "keep-alpha",
}
for _z in ("eldeon\\ejt01", "junon\\jd02", "junon\\jd03", "junon\\jg03", "junon\\jg04", "junon\\jg05",
           "junon\\jz01_1", "lunar\\lp01", "lunar\\lp02", "lunar\\lp03", "lunar\\lp04"):
    OVERRIDES["maps\\%s\\minimap.dds" % _z] = "take"


def index(root):
    """lower-case relative path -> real path, DDS only."""
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(".dds"):
                p = os.path.join(d, f)
                out[os.path.relpath(p, root).lower()] = p
    return out


def rgba(path):
    im = Image.open(path)
    im.load()
    return im.convert("RGBA")


def has_alpha(h):
    return h.compressed or bool(h.pf_flags & dds.DDPF_ALPHAPIXELS)


def block_means(a):
    h, w = a.shape[0] // 4 * 4, a.shape[1] // 4 * 4
    return a[:h, :w, :3].astype(np.float64).reshape(h // 4, 4, w // 4, 4, 3).mean(axis=(1, 3))


def dxt_decoded(a):
    h, w = a.shape[0] // 4 * 4, a.shape[1] // 4 * 4
    if not h or not w:
        return False
    b = a[:h, :w, :3].reshape(h // 4, 4, w // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3)
    packed = (b[..., 0].astype(np.int64) << 16) | (b[..., 1].astype(np.int64) << 8) | b[..., 2]
    s = np.sort(packed, axis=1)
    return float((1 + (np.diff(s, axis=1) != 0).sum(1) <= 4).mean()) >= DXT_DECODED


def compare(ours, theirs, their_alpha):
    """Metrics and verdict for one pair of RGBA images of the same size."""
    a, b = np.asarray(ours), np.asarray(theirs)
    d = block_means(a) - block_means(b)
    block = float(math.sqrt((d ** 2).mean()))
    worst = float(np.abs(d).max())
    mse = ((a[..., :3].astype(np.float64) - b[..., :3]) ** 2).mean()
    psnr = 99.0 if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    ours_opaque = int(a[..., 3].min()) >= 250
    if not their_alpha:
        alpha = "none" if ours_opaque else "lost"
    else:
        alpha = "differs" if not ours_opaque and float((np.abs(a[..., 3].astype(int) - b[..., 3]) > 64).mean()) > .01 else "ok"
    if block > MATCH_BLOCK or worst > WORST_BLOCK or alpha == "lost":
        verdict = "none"
    elif alpha == "differs":
        verdict = "doubtful"
    else:
        verdict = "match"
    return dict(block=round(block, 2), worst=round(worst, 1), psnr=round(psnr, 1), alpha=alpha, verdict=verdict)


def survey(max_size):
    os.makedirs(OUT, exist_ok=True)
    ours = index(DATA)
    srcs = [(name, index(root)) for name, root in SOURCES]
    crystal = index(CRYSTAL_SOURCE[1])
    plan, why = {}, Counter()
    for rel, path in sorted(ours.items()):
        if rel.startswith("control\\"):
            continue                  # UI sheets have their own tools
        h = dds.header(path)
        if h is None or not h.compressed:
            continue
        is_crystal = rel.startswith("avatar\\") and any(c in rel for c in CRYSTAL)
        if max(h.width, h.height) > max_size and not is_crystal or min(h.width, h.height) < 4:
            continue
        cands = [(CRYSTAL_SOURCE[0], crystal)] if is_crystal else srcs
        best = None
        for name, idx in cands:
            q = idx.get(rel)
            th = q and dds.header(q)
            if not th or th.compressed or (th.width, th.height) != (h.width, h.height):
                continue
            b = rgba(q)
            if dxt_decoded(np.asarray(b)):
                why["decoded-dxt copy in %s" % name] += 1
                continue
            m = compare(rgba(path), b, has_alpha(th))
            m.update(source=name, file=q, bits=th.bit_count, size=[h.width, h.height], ours_fourcc=h.fourcc.decode("latin-1"))
            if rel in OVERRIDES:
                m.update(verdict="match", override=OVERRIDES[rel])
            if m["verdict"] == "match":
                best = m
                break
            if best is None or (m["verdict"] == "doubtful" and best["verdict"] == "none"):
                best = m
        if best is None:
            why["no uncompressed copy"] += 1
            continue
        plan[rel] = best
    with open(PLAN, "w") as f:
        json.dump(dict(max_size=max_size, textures=plan), f, indent=1)
    write_summary(plan, why)
    write_sheets(plan, ours)


def write_summary(plan, why):
    lines = []
    v = Counter(m["verdict"] for m in plan.values())
    lines.append("verdicts: %s" % dict(v))
    lines.append("skipped: %s" % dict(why))
    take = [m for m in plan.values() if m["verdict"] == "match"]
    lines.append("by source (match): %s" % dict(Counter(m["source"] for m in take)))
    folders = Counter("\\".join(r.split("\\")[:2]) for r, m in plan.items() if m["verdict"] == "match")
    lines.append("by folder (match):")
    lines += ["  %4d %s" % (n, f) for f, n in folders.most_common()]
    extra = sum(m["size"][0] * m["size"][1] * 4 * 4 // 3 for m in take)
    lines.append("written size of the matches (32-bit, %d mips): ~%.1f MB" % (MIPS, extra / 1e6))
    lines.append("")
    lines.append("block distance of the matches: %s" % np.percentile([m["block"] for m in take], [50, 90, 99, 100]).round(2).tolist() if take else "")
    lines.append("doubtful / none:")
    for r, m in sorted(plan.items()):
        if m["verdict"] != "match":
            lines.append("  %-8s %-55s %s block %.2f worst %.0f alpha %s" % (m["verdict"], r, m["source"], m["block"], m["worst"], m["alpha"]))
    with open(os.path.join(OUT, "summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:6 + len(folders)]))
    print("details: %s" % os.path.join(OUT, "summary.txt"))


def write_sheets(plan, ours, per_sheet=40):
    """ours | copy pairs, each scaled to 128 px tall, 2 columns of pairs."""
    rows = sorted(plan.items(), key=lambda kv: ({"doubtful": 0, "none": 1, "match": 2}[kv[1]["verdict"]], kv[0]))
    T = 128
    for s in range(0, len(rows), per_sheet):
        chunk = rows[s:s + per_sheet]
        cols, cell_w, cell_h = 2, 2 * T + 16, T + 22
        sheet = Image.new("RGB", (cols * cell_w, math.ceil(len(chunk) / cols) * cell_h), (24, 24, 24))
        draw = ImageDraw.Draw(sheet)
        for i, (rel, m) in enumerate(chunk):
            x, y = (i % cols) * cell_w, (i // cols) * cell_h
            colour = {"match": (60, 170, 60), "doubtful": (230, 140, 30), "none": (110, 110, 110)}[m["verdict"]]
            for k, p in enumerate((ours[rel], m["file"])):
                im = rgba(p).convert("RGB")
                im = im.resize((max(1, im.width * T // im.height), T), Image.NEAREST if im.height <= T else Image.BILINEAR)
                im = im.crop((0, 0, min(im.width, T), T))
                sheet.paste(im, (x + 4 + k * (T + 4), y + 2))
            draw.rectangle([x + 2, y, x + 2 * T + 10, y + T + 4], outline=colour, width=2)
            draw.text((x + 4, y + T + 6), "%s %s %.1f" % (rel[-36:], m["source"], m["block"]), fill=(220, 220, 220))
        sheet.save(os.path.join(OUT, "sheet-%02d.png" % (s // per_sheet + 1)))


def mip_levels(img):
    """[mip 0, mip 1, ...] up to MIPS, each a 2x2 box average of the one before.

    Every channel is filtered on its own. Pillow resamples an RGBA image
    *premultiplied*, so wherever alpha is 0 the colour of the smaller levels is
    wiped to black -- and on ROSE avatar textures alpha is a specular mask, not
    coverage (body2_31020 is alpha 0 throughout). That shipped once (2026-10-22,
    172 of 1,313 textures: armour turning black as the camera zooms out, the
    same wash add-dds-mipmaps.py's WIC bug gave Oro's NPCs).
    """
    levels = [img]
    cover = is_coverage(img)
    while len(levels) < MIPS and min(levels[-1].size) > 1:
        size = (max(1, levels[-1].width // 2), max(1, levels[-1].height // 2))
        prev = levels[-1]
        if not cover:
            levels.append(Image.merge("RGBA", [c.resize(size, Image.BOX) for c in prev.split()]))
            continue
        # Cut-out alpha over a black fill: average colour over visible texels only,
        # or the fill bleeds into the edges (SW_PORTTREE004's leaves lost 25%).
        a = np.asarray(prev, np.float64)
        wgt = a[..., 3:] / 255.0
        rgb = np.asarray(Image.fromarray((a[..., :3] * wgt).round().astype(np.uint8)).resize(size, Image.BOX), np.float64)
        alpha = np.asarray(prev.getchannel("A").resize(size, Image.BOX), np.float64)[..., None]
        out = np.where(alpha > 0, rgb * 255.0 / np.maximum(alpha, 1), 0)
        levels.append(Image.fromarray(np.concatenate([np.clip(out.round(), 0, 255), alpha], 2).astype(np.uint8), "RGBA"))
    return levels


def is_coverage(img):
    """Alpha is cut-out coverage, not a specular mask: some texels are transparent and
    every transparent texel is black fill (a specular mask keeps real colour there)."""
    a = np.asarray(img)
    clear = a[..., 3] < 8
    return bool(clear.any()) and float(a[..., :3][clear].max(initial=0)) <= 8


def encode(img):
    """RGBA image -> 32-bit BGRA DDS with up to MIPS box-filtered levels."""
    levels = mip_levels(img)
    h = dds.bgra_header(img.width, img.height, mips=len(levels))
    body = b""
    for lv in levels:
        r, g, b, a = lv.split()
        body += Image.merge("RGBA", (b, g, r, a)).tobytes()
    return dds.build_header(h) + body


def read_levels(path):
    """Every level of a 32-bit BGRA DDS as (h, w, 4) RGBA uint8 arrays."""
    with open(path, "rb") as f:
        b = f.read()
    h = dds.parse_header(b)
    out, off = [], h.payload_offset
    for i in range(h.mips or 1):
        w, hh = max(1, h.width >> i), max(1, h.height >> i)
        a = np.frombuffer(b[off:off + w * hh * 4], np.uint8).reshape(hh, w, 4)[..., [2, 1, 0, 3]]
        out.append(a)
        off += w * hh * 4
    return out


def box_ok(big, small):
    """Is `small` a straight (not premultiplied) 2x2 box average of `big`, per channel?"""
    hh, w = small.shape[0] * 2, small.shape[1] * 2
    if big.shape[0] < hh or big.shape[1] < w:
        return False
    if (big.shape[0], big.shape[1]) != (hh, w):
        # odd side (93, 259, 639 px): the resize is not an aligned 2x2 box, so
        # compare each channel's mean -- the darkening this guards against moved it 15-100%
        a, b = big.reshape(-1, 4).mean(0), small.reshape(-1, 4).mean(0)
        return bool((np.abs(a - b) <= np.maximum(2.0, a * .02)).all())
    want = big[:hh, :w].astype(np.float64).reshape(small.shape[0], 2, small.shape[1], 2, 4).mean(axis=(1, 3))
    return float(np.abs(want - small).max()) <= 1.0


def source_image(rec, alpha_from):
    """What a texture should hold: the copy, made opaque if it has no alpha, or
    with the alpha of `alpha_from` (our original) for a keep-alpha override."""
    img = rgba(rec["file"])
    if rec.get("override") == "keep-alpha" or rec.get("keep_alpha"):
        img.putalpha(rgba(alpha_from).getchannel("A"))
    elif rec.get("alpha") == "none" or rec.get("opaque"):
        img.putalpha(255)
    return img


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            return json.load(f)
    return dict(written={})


def apply(dry, include_doubtful):
    with open(PLAN) as f:
        plan = json.load(f)["textures"]
    want = ("match", "doubtful") if include_doubtful else ("match",)
    ours = index(DATA)
    m = load_manifest()
    n = size_before = size_after = 0
    for rel, rec in sorted(plan.items()):
        if rec["verdict"] not in want:
            continue
        dst = ours[rel]
        img = source_image(rec, dst)
        blob = encode(img)
        size_before += os.path.getsize(dst)
        size_after += len(blob)
        n += 1
        if dry:
            continue
        bak = os.path.join(BACKUP, rel)
        if rel not in m["written"]:
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            shutil.copy2(dst, bak)
        with open(dst, "wb") as f:
            f.write(blob)
        m["written"][rel] = dict(source=rec["source"], file=rec["file"], opaque=rec["alpha"] == "none",
                                 keep_alpha=rec.get("override") == "keep-alpha")
    if not dry:
        os.makedirs(BACKUP, exist_ok=True)
        with open(MANIFEST, "w") as f:
            json.dump(m, f, indent=1)
    print("%s %d textures: %.1f MB -> %.1f MB (%+.1f MB)" % ("would write" if dry else "wrote", n,
          size_before / 1e6, size_after / 1e6, (size_after - size_before) / 1e6))


def rewrite():
    """Re-encode every texture the manifest records, from its recorded source (and
    our backed-up alpha for keep-alpha), after a change to encode()."""
    m = load_manifest()
    ours = index(DATA)
    for rel, rec in sorted(m["written"].items()):
        with open(ours[rel], "wb") as f:
            f.write(encode(source_image(rec, os.path.join(BACKUP, rel))))
    print("rewrote %d textures" % len(m["written"]))


def fix_mips(paths):
    """Rebuild a texture's mips from its own mip 0, written as 32-bit (mip 0 decoded
    exactly), for files whose shipped chain is darker than their top level."""
    m = load_manifest()
    for p in paths:
        rel = os.path.relpath(os.path.abspath(p), os.path.abspath(DATA)).lower()
        bak = os.path.join(BACKUP, rel)
        if rel not in m["written"]:
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            shutil.copy2(p, bak)
        rec = dict(source="own-mip0", file=os.path.abspath(bak), opaque=False, keep_alpha=False)
        with open(p, "wb") as f:
            f.write(encode(source_image(rec, bak)))
        m["written"][rel] = rec
        print("  rebuilt mips of %s (%s)" % (rel, "cut-out" if is_coverage(rgba(bak)) else "straight"))
    with open(MANIFEST, "w") as f:
        json.dump(m, f, indent=1)


def verify():
    m = load_manifest()
    ours = index(DATA)
    bad = 0
    for rel, rec in sorted(m["written"].items()):
        path = ours.get(rel)
        h = path and dds.header(path)
        if not h or h.compressed or h.bit_count != 32 or h.is_dx10 or not 1 <= h.mips <= MIPS:
            print("  %s: not a 32-bit legacy-header DDS with mips" % rel)
            bad += 1
            continue
        src = source_image(rec, os.path.join(BACKUP, rel))
        if (h.width, h.height) != src.size or os.path.getsize(path) < 128 + h.width * h.height * 4:
            print("  %s: size mismatch" % rel)
            bad += 1
            continue
        levels = read_levels(path)
        if not np.array_equal(levels[0], np.asarray(src)):
            print("  %s: mip 0 differs from %s" % (rel, rec["file"]))
            bad += 1
        elif is_coverage(src):
            vis = [l[..., :3][l[..., 3] > 127].mean() for l in levels if (l[..., 3] > 127).any()]
            # natural detail averaging moves this a few % (butterfly wings -4%, a cap
            # whose visible part is 4% of the texture -8%); fill bleed moved it 25%
            if vis and min(vis) < vis[0] * .90 and min(src.size) >= 16:
                print("  %s: cut-out texture, a lower mip's visible texels are darker" % rel)
                bad += 1
        elif not all(box_ok(levels[i], levels[i + 1]) for i in range(len(levels) - 1)):
            print("  %s: a lower mip is not a box average of the one above (premultiplied/darkened?)" % rel)
            bad += 1
    print("verify: %d textures, %d problems" % (len(m["written"]), bad))
    return bad == 0


def restore(only=None):
    """Put the originals back: all of them, or only the `only` paths (relative to
    data/3DDATA, any case), which also leave the manifest."""
    m = load_manifest()
    ours = index(DATA)
    rels = sorted(m["written"]) if not only else [r.lower().replace("/", "\\") for r in only]
    for rel in rels:
        if rel not in m["written"]:
            raise SystemExit("%s was not written by this tool" % rel)
        shutil.copy2(os.path.join(BACKUP, rel), ours[rel])
        del m["written"][rel]
    print("restored %d textures" % len(rels))
    if m["written"]:
        with open(MANIFEST, "w") as f:
            json.dump(m, f, indent=1)
    else:
        os.remove(MANIFEST)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--survey", action="store_true", help="match and write the review sheets (writes only build/)")
    ap.add_argument("--apply", action="store_true", help="write the surveyed plan.json matches into data/")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", nargs="*", metavar="REL", help="put the originals back: all, or these paths under data/3DDATA")
    ap.add_argument("--rewrite", action="store_true", help="re-encode every texture in the manifest from its source")
    ap.add_argument("--fix-mips", nargs="+", metavar="DDS", help="rebuild these files' mips from their own mip 0")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-doubtful", action="store_true")
    ap.add_argument("--max-size", type=int, default=MAX_SIZE, help="largest side to consider (default %d)" % MAX_SIZE)
    args = ap.parse_args()
    if args.restore is not None:
        return restore(args.restore)
    if args.rewrite:
        return rewrite()
    if args.fix_mips:
        return fix_mips(args.fix_mips)
    if args.verify:
        return sys.exit(0 if verify() else 1)
    if args.apply:
        return apply(args.dry_run, args.include_doubtful)
    if args.survey:
        return survey(args.max_size)
    ap.print_help()


if __name__ == "__main__":
    main()
