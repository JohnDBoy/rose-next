"""Write a build into the game database as a real character, to check the simulator in game.

One transaction: the account (created, or its password and access level updated), the
character row (stats, level, job, skills, hotbar), and one `item` + `inventory` row per
equipped item and for the ammo stack. The layout is what `gs_threadsql.cpp` saves and
loads:

  * inventory slot = CInventory::m_ItemLIST index: 1..11 are the equip slots
    (EQUIP_IDX_*), ammo sits at INVENTORY_SHOT_ITEM0 + shot type = 132 + (0 arrow,
    1 bullet, 2 throw);
  * item.stat_id = m_nGEM_OP (an option <= 300 counts when `appraisal`, a gem > 300
    when `socket`); durability is the 7-bit m_cDurability; lifespan 1000 = full;
  * skills = the 120-slot m_nSkillINDEX array: page = SKILL_TAB_TYPE (clamped to 0..3,
    tagSkillAbility::PageOf), first empty slot of the page (Skill_FindEmptySlot), after
    the default basics;
  * hotbar = [{"type": 3 (SKILL_ICON), "skill_slot": n}, ...] x 64.

The server's own `Cal_BattleAbility` recomputes every derived stat at login; HP and MP
are written at the simulator's maximum so the character starts full.

Talks to PostgreSQL through psql (like scripts/create-account.ps1), using the
connection_string of a server.toml.
"""
import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
import uuid

from .data import ROOT, SHOT_BY_WEAPON
from .player import STAT_KEYS, total_bonus_points
from .sim import Simulation

DEFAULT_SKILLS = [11, 12, 16, 19, 20, 21, 7001]   # column default (migrations 0001/0002)
SHOT_SLOT0 = 132                                  # INVENTORY_SHOT_ITEM0
PAGE = 30                                         # MAX_LEARNED_SKILL_PER_PAGE
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{2,15}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9@._-]{1,30}$")


def find_psql():
    if os.environ.get("PGBIN"):
        p = os.path.join(os.environ["PGBIN"], "psql.exe")
        if os.path.exists(p):
            return p
    base = r"C:\Program Files\PostgreSQL"
    if os.path.isdir(base):
        for v in sorted(os.listdir(base), key=lambda x: int(re.sub(r"\D", "0", x) or 0),
                        reverse=True):
            p = os.path.join(base, v, "bin", "psql.exe")
            if os.path.exists(p):
                return p
    return shutil.which("psql")


def pg_env(server_toml):
    text = open(server_toml, encoding="utf-8").read()
    m = re.search(r'connection_string\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit(f"no connection_string in {server_toml}")
    u = re.match(r"postgres(?:ql)?://([^:@/]+)(?::([^@/]*))?@([^:/]+)(?::(\d+))?/([^?]+)",
                 m.group(1))
    if not u:
        raise SystemExit("cannot parse connection_string")
    user, pw, host, port, db = u.groups()
    return dict(os.environ, PGUSER=user, PGPASSWORD=pw or "", PGHOST=host,
                PGPORT=port or "5432", PGDATABASE=db)


def run_sql(sql, server_toml):
    psql = find_psql()
    if not psql:
        raise SystemExit("psql not found; set PGBIN to your PostgreSQL bin folder")
    r = subprocess.run([psql, "--no-psqlrc", "-q", "-v", "ON_ERROR_STOP=1", "-f", "-"],
                       input=sql, env=pg_env(server_toml), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"psql failed:\n{r.stderr.strip()}")
    return r.stdout


def password_hash(password):
    """sha256(sha256(plaintext) + salt), as create-account.ps1 and the login server."""
    salt = "".join(random.choice(string.ascii_lowercase) for _ in range(16))
    inner = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hashlib.sha256((inner + salt).encode("utf-8")).hexdigest(), salt


def skill_slots(gd, rows):
    """Lay learned skill rows into the 120-slot array the way Skill_LEARN would."""
    slots = [0] * 120
    for i, r in enumerate(DEFAULT_SKILLS):
        slots[i] = r
    seen = {gd.sk(r, 1) or r for r in DEFAULT_SKILLS}
    placed = {}
    for r in rows:
        group = gd.sk(r, 1) or r
        if group in seen:
            continue
        seen.add(group)
        tab = gd.sk(r, 4)
        page = tab if 0 <= tab < 4 else 0
        for i in range(page * PAGE, page * PAGE + PAGE):
            if not slots[i]:
                slots[i] = r
                placed[r] = i
                break
        else:
            raise SystemExit(f"skill page {page} is full; cannot learn {gd.name('LIST_SKILL', r)}")
    return slots, placed


def _q(s):
    return "'" + str(s).replace("'", "''") + "'"


def build_sql(gd, build, account, password, name, access, replace):
    if not NAME_RE.match(name):
        raise SystemExit("character name: 3-16 letters/digits, starting with a letter")
    if not EMAIL_RE.match(account):
        raise SystemExit("account: 1-30 chars of letters, digits, @ . _ -")
    if len(password) < 8:   # client: MIN_PASSWORD_LENGTH (interface/externalui/clogin.h)
        raise SystemExit("password: the client refuses fewer than 8 characters")
    sim = Simulation(gd, build, 1)
    st, p = sim.stats, sim.make_player()
    pw, salt = password_hash(password)

    learned = list(build.skills) + list(build.rotation) \
        + [b["skill"] for b in build.buffs if not b["caster_int"]]
    skills, placed = skill_slots(gd, learned)
    hot = [{"type": 0, "skill_slot": 0} for _ in range(64)]
    bar = [r for r in list(build.rotation) + [b["skill"] for b in build.buffs] if r in placed]
    for i, r in enumerate(bar[:8]):
        hot[i] = {"type": 3, "skill_slot": placed[r]}

    items = []      # (slot, type, no, gem, grade, durability, lifespan, appraisal, socket, qty)
    for slot_name, it in build.equip.items():
        if not it.id:
            continue
        dur = it.durability if it.durability is not None else gd.item_durability(it.itype, it.id)
        dur = max(0, min(127, int(dur)))
        items.append((it.equip_idx, it.itype, it.id, it.gem, it.grade, dur, 1000,
                      bool(it.gem and it.gem <= 300), bool(it.gem and it.gem > 300), 1))
    wtype = gd.weapon_type(build.equip["weapon"].id) if build.equip["weapon"].id else 0
    shot = SHOT_BY_WEAPON.get(wtype)
    if shot is not None and build.ammo:
        items.append((SHOT_SLOT0 + shot, 12, build.ammo, 0, 0, 0, 0, False, False, 999))

    spare = max(0, total_bonus_points(build.level) - build.points_spent())
    stats = {k: build.stats[k] for k in STAT_KEYS}

    lines = ["BEGIN;"]
    lines.append(
        f"INSERT INTO account (email, password, salt, access_level) VALUES "
        f"({_q(account)}, {_q(pw)}, {_q(salt)}, {int(access)}) ON CONFLICT (email) DO UPDATE "
        f"SET password = EXCLUDED.password, salt = EXCLUDED.salt, "
        f"access_level = EXCLUDED.access_level;")
    if replace:
        lines.append(
            f"DELETE FROM item WHERE id IN (SELECT item_id FROM inventory WHERE owner_id IN "
            f"(SELECT id FROM character WHERE name = {_q(name)}));")
        lines.append(f"DELETE FROM character WHERE name = {_q(name)};")
    lines.append("DO $$ DECLARE cid integer; iid integer; BEGIN")
    lines.append(
        "INSERT INTO character (account_email, name, gender_id, job_id, level, hp, mp, "
        "max_hp, max_mp, str, dex, intt, con, cha, sen, stat_points, skill_points, "
        "union_id, skills, hotbar) VALUES ("
        f"{_q(account)}, {_q(name)}, {1 if build.female else 0}, {build.job}, {build.level}, "
        f"{p.max_hp}, {p.max_mp}, {p.max_hp}, {p.max_mp}, {stats['STR']}, {stats['DEX']}, "
        f"{stats['INT']}, {stats['CON']}, {stats['CHARM']}, {stats['SENSE']}, {spare}, 0, "
        f"{build.union}, {_q(json.dumps(skills))}::jsonb, {_q(json.dumps(hot))}::jsonb) "
        "RETURNING id INTO cid;")
    for slot, itype, no, gem, grade, dur, life, appr, sock, qty in items:
        lines.append(
            "INSERT INTO item (uuid, game_data_id, type_id, stat_id, grade, durability, "
            f"lifespan, appraisal, socket, crafted) VALUES ({_q(uuid.uuid4())}, {no}, {itype}, "
            f"{gem}, {grade}, {dur}, {life}, {str(appr).lower()}, {str(sock).lower()}, false) "
            "RETURNING id INTO iid;")
        lines.append(f"INSERT INTO inventory (owner_id, item_id, slot, quantity) VALUES "
                     f"(cid, iid, {slot}, {qty});")
    lines.append("END $$;")
    lines.append("COMMIT;")
    summary = dict(account=account, name=name, job=build.job, level=build.level, hp=p.max_hp,
                   mp=p.max_mp, items=len(items), skills=sum(1 for x in skills if x),
                   hotbar=len(bar[:8]), spare_points=spare,
                   expected=dict(atk=p.total_atk, hit=p.total_hit, df=p.get_def,
                                 res=p.get_res, avoid=p.get_avoid, crit=p.get_crit,
                                 aspd=p.total_aspd, atk_before_bonus=st.attack_power))
    return "\n".join(lines) + "\n", summary


def default_server_toml():
    for rel in ("Exes/server.toml", "bin/release/server.toml"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            return p
    raise SystemExit("no server.toml found; pass --server-toml")


def seed(gd, build, account, password, name, access=2048, replace=False, dry_run=False,
         server_toml=None):
    sql, summary = build_sql(gd, build, account, password, name, access, replace)
    if dry_run:
        return sql, summary
    run_sql(sql, server_toml or default_server_toml())
    return None, summary
