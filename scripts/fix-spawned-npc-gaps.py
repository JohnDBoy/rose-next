"""Close the four gaps scripts/audit-spawned-npcs.py found on its first run (2026-10-12).

    python scripts/fix-spawned-npc-gaps.py --dry-run
    python scripts/fix-spawned-npc-gaps.py
    python scripts/fix-spawned-npc-gaps.py --verify
    python scripts/fix-spawned-npc-gaps.py --restore

1. **Sikuku Elite Fighter 562 has no LIST_NPC.CHR entry** -- in every dump we
   own, so it was never a model that could be "grabbed". Turak's AI summons it
   (SummonMaster) and the summon was invisible and unclickable. But our own
   table carries the same monster twice more: rows 540 and 1708 are "Sikuku
   Elite Fighter" with the same `s_fighter05.mon`, models 349/350 on skeleton
   97. Row 562 gets a copy of row 540's entry.
2. **[Astronomer] Boyren 1175 has no CHR entry** and an empty model column; no
   dump has a Boyren (the id is a different NPC in every lineage). He is placed
   in Mount Eruca, so he gets the astronomer the 667 build ships, "[Stargazer]
   Nubo" (row 2129 there, `Bond.mon`): skeleton, two parts, wait motion,
   brought across with `rosedata.import_characters`, which remaps every index
   and copies the art.
3. **LIST_WEAPON.ZSC object 1158 has no parts** -- the Ikaness Warden's weapon.
   667's row 1158 is the same item by name and has the model
   (`MOB_ICANES_WARDEN.zms` + texture); the object is rebuilt from it, meshes
   and materials deduped by path, the two files copied.
4. **Object 1156 has no parts** -- the Evil Fairy's weapon. The Fairy came from
   Jrose (import-karkia.py copies LIST_NPC cols 0-42 verbatim, hand included),
   so Jrose's object 1156 (`mob_can.zms`, `mob_flower.dds`, both already here)
   is the right source; 667's 1156 is a different item.

Idempotent: a gap already closed is skipped. Before the first write the four
tables (LIST_NPC.CHR, PART_NPC.ZSC, LIST_WEAPON.ZSC, LIST_NPC.STB) are copied
to `build/spawned-npc-gaps/orig/`, and the manifest records their hashes after
the run; --restore copies the originals back only while the tables still hash
as this script left them, so a later script's change is never silently undone
(the whole-file backup hazard). `import_characters` leaves a `.bak` beside the
files it writes; this script moves them into the build folder, because
pack.ps1 refuses to bake while one sits under data/.

Server and client both load LIST_NPC.CHR: restart the servers and re-bake.
"""
import argparse
import copy
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rosedata as oro  # noqa: E402
from rosefmt.zsc import serialize_object  # noqa: E402

REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, "data")
TESTCLIENTS = r"C:\Users\Thomas\Desktop\Testclients"
SRC_667 = os.path.join(TESTCLIENTS, "667", "extracted data")
SRC_JROSE = os.path.join(TESTCLIENTS, "Jrose")
BUILD = os.path.join(REPO, "build", "spawned-npc-gaps")
MANIFEST = os.path.join(BUILD, "manifest.json")

NPC_STB = r"3DDATA\STB\LIST_NPC.STB"
WEAPON_ZSC = r"3DDATA\WEAPON\LIST_WEAPON.ZSC"
NPC_MON_COL = 1

CLONE_CHR = {562: 540}                       # our row <- our row
IMPORT_CHR = {1175: ("Boyren", SRC_667, 2129, "Bond.mon")}   # our row <- (label, dump, its row, mon file)
WEAPON_OBJECTS = {1158: SRC_667, 1156: SRC_JROSE}            # our object <- dump's same index
TABLES = (oro.NPC_CHR_REL, oro.PART_NPC_ZSC_REL, WEAPON_ZSC, NPC_STB)
ORIG = os.path.join(BUILD, "orig")


def sha(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def take_originals(dry):
    """Whole-file copies of the four tables, once, before anything is written."""
    if dry:
        return
    os.makedirs(ORIG, exist_ok=True)
    for rel in TABLES:
        dst = os.path.join(ORIG, os.path.basename(rel))
        if not os.path.exists(dst):
            shutil.copyfile(P(rel), dst)


def P(rel):
    return oro.rel_path(DATA, rel)


# ------------------------------------------------------------------ ZSC
def chr_json(entry):
    if entry is None:
        return None
    return {"skel": entry["skel"], "name": entry["name"].decode("latin-1"),
            "models": entry["models"], "anims": entry["anims"], "effects": entry["effects"]}


def chr_from_json(d):
    if d is None:
        return None
    return dict(skel=d["skel"], name=d["name"].encode("latin-1"), models=list(d["models"]),
                anims=[tuple(x) for x in d["anims"]], effects=[tuple(x) for x in d["effects"]])


def zsc_write(z, path, extra_meshes=(), extra_mats=()):
    """The table with meshes/materials appended and the object section rebuilt
    from ``z.objects`` (so a replaced object lands at its index)."""
    out = [struct.pack("<H", len(z.meshes) + len(extra_meshes)), z.d[2:z.mesh_end]]
    out += [m + b"\x00" for m in extra_meshes]
    out += [struct.pack("<H", len(z.materials) + len(extra_mats)), z.d[z.mesh_end + 2:z.mat_end]]
    out += [p + b"\x00" + flags for p, flags in extra_mats]
    out += [z.d[z.mat_end:z.objcnt_pos], struct.pack("<H", len(z.objects)), z.objects_blob()]
    with open(path, "wb") as fh:
        fh.write(b"".join(out))


def fill_weapon_object(our, src, src_root, idx, dry):
    """Rebuild our object ``idx`` from the source's, deduping meshes and
    materials by path and copying the files we lack. Returns a note."""
    cyl, sparts, sdummies, sbb = src.objects[idx]
    mesh_idx = {oro.norm(m): i for i, m in enumerate(our.meshes)}
    mat_idx = {oro.norm(p): i for i, (p, _) in enumerate(our.materials)}
    new_meshes, new_mats, files = [], [], set()
    parts = []
    for mid, tid, props in sparts:
        mk = oro.norm(src.meshes[mid])
        if mk not in mesh_idx:
            mesh_idx[mk] = len(our.meshes) + len(new_meshes)
            new_meshes.append(src.meshes[mid])
        tk = oro.norm(src.materials[tid][0])
        if tk not in mat_idx:
            mat_idx[tk] = len(our.materials) + len(new_mats)
            new_mats.append(src.materials[tid])
        files.add(src.meshes[mid].decode("latin-1"))
        files.add(src.materials[tid][0].decode("latin-1"))
        parts.append((mesh_idx[mk], mat_idx[tk], props))
    our.objects[idx] = (cyl, parts, sdummies, sbb)
    oro.copy_files(files, src_root, DATA, dry, "weapon %d art" % idx)
    if not dry:
        zsc_write(our, P(WEAPON_ZSC), new_meshes, new_mats)
        our.meshes.extend(new_meshes)
        our.materials.extend(new_mats)
        # re-read so later objects see the new tables
    return "%d parts, +%d meshes, +%d materials" % (len(parts), len(new_meshes), len(new_mats))


def move_baks(dry):
    for rel in (oro.NPC_CHR_REL, oro.PART_NPC_ZSC_REL):
        bak = P(rel) + ".bak"
        if os.path.exists(bak):
            dst = os.path.join(BUILD, os.path.basename(bak))
            if not dry:
                os.makedirs(BUILD, exist_ok=True)
                shutil.move(bak, dst)
            print("    moved %s -> build/spawned-npc-gaps/ (pack.ps1 refuses .bak under data/)" % os.path.basename(bak))


# ------------------------------------------------------------------ stages
def run(dry):
    os.makedirs(BUILD, exist_ok=True)
    take_originals(dry)
    man = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"chr": {}, "weapon": {}, "npc_mon": {}}
    chr_ = oro.Chr(P(oro.NPC_CHR_REL))
    npc = oro.Stb(P(NPC_STB))

    # 1. the clone
    for dst, src in CLONE_CHR.items():
        if chr_.chars[dst] is not None:
            print("  CHR %d already has an entry (skipped)" % dst)
            continue
        man["chr"].setdefault(str(dst), chr_json(chr_.chars[dst]))
        chr_.chars[dst] = copy.deepcopy(chr_.chars[src])
        print("  CHR %d <- copy of row %d (%s, models %s)" % (dst, src, npc.s(src, 0), chr_.chars[src]["models"]))
    if not dry:
        chr_.save(dry, keep_backup=False)

    # 2. the import
    for dst, (label, root, srow, mon) in IMPORT_CHR.items():
        chr_ = oro.Chr(P(oro.NPC_CHR_REL))
        if chr_.chars[dst] is not None:
            print("  CHR %d (%s) already has an entry (skipped)" % (dst, label))
        else:
            man["chr"].setdefault(str(dst), None)
            parts_before = len(oro.Zsc(P(oro.PART_NPC_ZSC_REL)).objects)
            man.setdefault("part_npc_objects_before", parts_before)
            print("  CHR %d (%s) <- %s row %d" % (dst, label, os.path.basename(os.path.dirname(root)) or root, srow))
            oro.import_characters([dst], DATA, root, dry, label, src_of={dst: srow})
            move_baks(dry)
        if npc.s(dst, NPC_MON_COL).strip() != mon:
            man["npc_mon"].setdefault(str(dst), npc.s(dst, NPC_MON_COL))
            npc.set(dst, NPC_MON_COL, mon)
            print("  LIST_NPC %d col %d <- %r" % (dst, NPC_MON_COL, mon))
            if not dry:
                npc.save(dry, keep_backup=False)

    # 3. the weapons
    for idx, root in WEAPON_OBJECTS.items():
        our = oro.Zsc(P(WEAPON_ZSC))
        if our.objects[idx][1]:
            print("  LIST_WEAPON.ZSC object %d already has parts (skipped)" % idx)
            continue
        src = oro.Zsc(oro.rel_path(root, WEAPON_ZSC))
        if not src.objects[idx][1]:
            raise SystemExit("source object %d has no parts either" % idx)
        man["weapon"].setdefault(str(idx), {"object": serialize_object(our.objects[idx]).hex(),
                                            "meshes": len(our.meshes), "materials": len(our.materials)})
        note = fill_weapon_object(our, src, root, idx, dry)
        print("  LIST_WEAPON.ZSC object %d <- %s: %s" % (idx, os.path.basename(os.path.dirname(root)) or root, note))

    if not dry:
        man["after"] = {os.path.basename(rel): sha(P(rel)) for rel in TABLES}
        with open(MANIFEST, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
    print("  dry run, nothing written" if dry else "  done -- restart the servers and re-bake")


def verify():
    ok = True
    chr_ = oro.Chr(P(oro.NPC_CHR_REL))
    files = set()
    for dp, _d, fs in os.walk(os.path.join(DATA, "3DDATA")):
        for f in fs:
            files.add(oro.norm(os.path.relpath(os.path.join(dp, f), DATA)))
    for i in list(CLONE_CHR) + list(IMPORT_CHR):
        e = chr_.chars[i]
        if e is None:
            print("  FAIL CHR %d: no entry" % i); ok = False; continue
        skel = chr_.skeletons[e["skel"]]
        print("  ok   CHR %d: skel %s, models %s, %d anims" % (i, skel.decode("latin-1"), e["models"], len(e["anims"])))
        if oro.norm(skel) not in files:
            print("  FAIL CHR %d: skeleton missing" % i); ok = False
    z = oro.Zsc(P(WEAPON_ZSC))
    for idx in WEAPON_OBJECTS:
        parts = z.objects[idx][1]
        if not parts:
            print("  FAIL LIST_WEAPON.ZSC %d: no parts" % idx); ok = False; continue
        for mid, tid, _p in parts:
            m, t = z.meshes[mid], z.materials[tid][0]
            for rel in (m, t):
                if oro.norm(rel) not in files:
                    print("  FAIL LIST_WEAPON.ZSC %d: missing %s" % (idx, rel.decode("latin-1"))); ok = False
        print("  ok   LIST_WEAPON.ZSC %d: %d parts, %s" % (idx, len(parts), z.meshes[parts[0][0]].decode("latin-1")))
    print("verify:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def restore():
    """Copy the originals back, only while the tables still hash as the run left them."""
    if not os.path.exists(MANIFEST):
        raise SystemExit("nothing to restore (no manifest)")
    man = json.load(open(MANIFEST))
    for rel in TABLES:
        name = os.path.basename(rel)
        if sha(P(rel)) != man.get("after", {}).get(name):
            raise SystemExit("%s changed since this script wrote it: not restoring (whole-file backup hazard)" % name)
        if not os.path.exists(os.path.join(ORIG, name)):
            raise SystemExit("missing original %s" % name)
    for rel in TABLES:
        name = os.path.basename(rel)
        shutil.copyfile(os.path.join(ORIG, name), P(rel))
        print("  %s restored" % name)
    os.remove(MANIFEST)
    print("  restored (the copied weapon art files are left in place; nothing references them)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.verify:
        return verify()
    if a.restore:
        restore()
        return 0
    run(a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
