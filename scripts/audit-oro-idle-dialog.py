"""Which Oro NPCs open no dialog at all, now that the quests are gone. Read-only.

The quest removal leaves every EM7x/EM8x .CON in place, and a dialog whose
greetings all sit behind a quest-state check renders nothing: CEvent's root loop
walks menu 0, runs each node's check function, and a speech node (type 1/2)
whose check passes opens the window with its LTB text. No passing speech node
with text = a click that does nothing ("I don't think I can talk to them"). See
scripts/unlock-karkia-idle-dialog.py for the mechanism and the fix.

This is the survey that decides which NPCs need that fix. For every NPC placed
by the 667 maps it decodes menu 0, evaluates each check function under the
shipped lua4.exe with the quest bindings stubbed the way the game now answers
them (no quest triggers exist, so QF_checkQuestCondition is false; user switches
are 0; the fate is probed both ways), and reports the speech nodes that pass and
carry English text.

    python scripts/audit-oro-idle-dialog.py            # report
    python scripts/audit-oro-idle-dialog.py --json out # machine-readable
"""
import argparse
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
EVENT = os.path.join(DATA, "3DDATA", "EVENT")
LUA4 = os.path.join(ROOT, "bin", "release", "thirdparty", "lua4.exe")
MAPS = os.path.join(DATA, "3DDATA", "MAPS", "ORO")
LTB_ENGLISH_COL = 2                 # GetEventString(id) = GetMbcsString(lang+1, id), EN lang 1

CHECK_OFF, CLICK_OFF, FUNC_LEN, NODE = 12, 44, 32, 80
SPEECH_TYPES = (1, 2)
QEX_MAGIC = b"QEX1"


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [fname]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return mod


import rosedata as oro  # the shared data layer (was import-oro.py)
fate = load("import_oro_fate", "import-oro-fate.py")


def cstr(b, o, n):
    f = b[o:o + n]
    z = f.find(b"\0")
    return f[:z if z >= 0 else n].decode("latin-1")


def menu_nodes(blob, index):
    """[(type, check, click, str_id)] of menu collection `index`, decoded."""
    conv_off, = struct.unpack_from("<I", blob, 516)
    _mn, _mo, menu_num, menu_off = struct.unpack_from("<iIiI", blob, 524)
    if not 0 <= index < menu_num:
        return []
    base = conv_off + menu_off
    mmt, = struct.unpack_from("<I", blob, base + index * 4)
    off = base + mmt
    length, num_sub = struct.unpack_from("<ii", blob, off)
    key = (num_sub if num_sub & 1 else length) & 0xFF
    coll = bytearray(blob[off:off + length])
    for k in range(8, len(coll)):
        coll[k] ^= key
    out = []
    for j in range(max(0, num_sub)):
        o, = struct.unpack_from("<I", coll, 8 + j * 4)
        if o + NODE > len(coll):
            break
        typ, = struct.unpack_from("<i", coll, o + 4)
        out.append((typ, cstr(coll, o + CHECK_OFF, FUNC_LEN),
                    cstr(coll, o + CLICK_OFF, FUNC_LEN),
                    struct.unpack_from("<i", coll, o + 76)[0]))
    return out


HARNESS = """
ARUA = ARUA or 0
HEBARN = HEBARN or 0
-- everything the game cannot answer any more answers "no"
settagmethod(tag(nil), "getglobal", function(name) return function(...) return 0 end end)
function QF_hasAruaFate() return ARUA end
function QF_hasHebarnFate() return HEBARN end
function QF_hasFate() if ARUA > 0 or HEBARN > 0 then return 1 end return 0 end
function QF_checkQuestCondition(t)
  if t == "Arua_Skill" then return ARUA end
  if t == "Hebarn_Skill" then return HEBARN end
  return 0
end
function QF_getUserSwitch(n) return 0 end
function QF_findQuest(q) return -1 end
function QF_getQuestCount() return 0 end
function QF_getEventOwner(h) return 1 end
function GF_GetTarget() return 1 end
function GF_getVariable(n) return 0 end
function QF_getNpcQuestZeroVal(n) return 0 end
function QF_getEpisodeVAR(n) return 0 end
function QF_getJobVAR(n) return 0 end
function QF_getPlanetVAR(n) return 0 end
function QF_getUnionVAR(n) return 0 end
function QF_getQuestVar(a, b) return 0 end
function QF_getQuestSwitch(a, b) return 0 end
function QF_getQuestItemQuantity(a, b) return 0 end
function QF_getSkillLevel(s) if s == 2880 then return ARUA end if s == 2881 then return HEBARN end return 0 end
"""


def probe(lua_blob, appendix, funcs, arua, hebarn):
    """{check name: 1/0} for the given fate state, via lua4."""
    if not funcs:
        return {}
    tmp = tempfile.mkdtemp()
    main_blob = os.path.join(tmp, "main.lub")
    open(main_blob, "wb").write(lua_blob)
    script = os.path.join(tmp, "run.lua")
    with open(script, "w", encoding="latin-1") as fh:
        fh.write(HARNESS)
        fh.write(f"ARUA={arua} HEBARN={hebarn}\n")
        fh.write('dofile("%s")\n' % main_blob.replace("\\", "/"))
        if appendix:
            fh.write(appendix.decode("latin-1") + "\n")
        for f in funcs:
            # Lua 4: call(func, args, "x") returns the results, or nil on error
            fh.write(f'do local v = call({f}, {{}}, "x")\n'
                     f'   if v == nil then v = 0 end\n'
                     f'   print("R {f} "..tostring(v)) end\n')
    r = subprocess.run([LUA4, script], capture_output=True, text=True)
    out = {}
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith("R "):
            _, name, v = line.split(None, 2)
            out[name] = v
    return out


def placements():
    """{npc id: .CON basename} from the MOB lumps of every Oro map."""
    out = {}
    for folder in sorted(os.listdir(MAPS)):
        d = os.path.join(MAPS, folder)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(".ifo"):
                continue
            buf, bounds = oro.read_ifo(os.path.join(d, f))
            objs, _ = oro.read_lump(buf, bounds, oro.LUMP_MOB)
            for o in objs or []:
                n = o["extra"][4]
                out[o["obj_id"]] = o["extra"][5:5 + n].decode("latin-1")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json")
    args = ap.parse_args()
    if not os.path.exists(LUA4):
        sys.exit(f"{LUA4} not built")
    npc = oro.Stb(os.path.join(DATA, "3DDATA", "STB", "LIST_NPC.STB"))
    ltb = oro.Ltb(os.path.join(DATA, oro.CON_LTB_REL))
    on_disk = {f.lower(): f for f in os.listdir(EVENT)}
    report = {}
    for nid, con in sorted(placements().items()):
        name = npc.get(nid, 0).decode("latin-1")
        entry = {"npc": nid, "name": name, "con": con, "status": "", "speech": []}
        report[nid] = entry
        if not con or con.lower() == "empty":
            entry["status"] = "no dialog (EMPTY)"
            continue
        real = on_disk.get(con.lower())
        if not real:
            entry["status"] = "MUTE: .CON file absent"
            continue
        blob = open(os.path.join(EVENT, real), "rb").read()
        _hdr, lua, appendix = fate.con_split(blob)
        nodes = menu_nodes(blob, 0)
        checks = sorted({c for _t, c, _k, _s in nodes if c})
        results = {}
        for label, a, h in (("nofate", 0, 0), ("arua", 1, 0), ("hebarn", 0, 1)):
            results[label] = probe(lua, appendix, checks, a, h)
        speech = []
        for typ, check, click, sid in nodes:
            if typ not in SPEECH_TYPES:
                continue
            text = ""
            if 0 < sid < len(ltb.rows) and ltb.rows[sid][LTB_ENGLISH_COL]:
                text = ltb.rows[sid][LTB_ENGLISH_COL].decode("utf-16-le", "replace").rstrip("\0")
            passes = {k: (not check) or v.get(check) not in ("0", "nil", "-1", None)
                      for k, v in results.items()}
            speech.append({"check": check, "str_id": sid, "text": text[:60],
                           "passes": passes})
        entry["speech"] = speech
        audible = {k: any(s["passes"][k] and s["text"] for s in speech) for k in results}
        if all(audible.values()):
            entry["status"] = "ok"
        elif not any(audible.values()):
            entry["status"] = "MUTE"
        else:
            entry["status"] = "mute for " + ", ".join(k for k, v in audible.items() if not v)
    width = max(len(e["name"]) for e in report.values()) + 2
    for nid, e in sorted(report.items()):
        print(f"{nid:5d} {e['name']:<{width}} {e['con']:<18} {e['status']}")
        if e["status"].startswith(("MUTE", "mute")):
            for s in e["speech"]:
                p = "".join("Y" if s["passes"][k] else "." for k in ("nofate", "arua", "hebarn"))
                print(f"      [{p}] check={s['check'] or '-':<24} {s['str_id']:6d} {s['text']!r}")
    mute = [n for n, e in report.items() if e["status"].startswith(("MUTE", "mute"))]
    print(f"\n{len(report)} NPCs, {len(mute)} need attention: {mute}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)


if __name__ == "__main__":
    main()
