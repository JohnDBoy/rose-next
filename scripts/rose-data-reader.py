"""Read STB/STL tables from *any* ROSE data dump, ours or a reference client.

The codecs are scripts/rosefmt (Stb, Stl); this module is the survey layer.
Our other scripts used to carry a private STB parser tuned to our own files. That is
fine until you point one at a foreign dump and it silently produces nothing,
because the reference clients differ from us in three ways that are invisible
until you hit them:

  * **Encoding.** Ours is latin-1. Jrose is Shift-JIS (cp932), RoseZA is Korean.
    Decoding with the wrong codec does not raise -- it yields mojibake that looks
    like a corrupt file rather than a wrong codec.
  * **STL dialect.** We write `NRST01`/`ITST01`/`QEST01`, which carry a language
    table and a per-entry offset table. Older clients (Jrose included) write
    `N_NUM`/`I_NUM`/`Q_NUM`, which have *neither* -- the entries follow the key
    table directly. A modern-only parser reads the first varint of the string
    data as a language count and asks for an 8 GB buffer.
  * **The STL key column moves.** We keep it at LIST_WEAPON column 45. Jrose puts
    it in the *last* column of each item table. Hardcoding 45 gets you a
    plausible-looking wrong string, not an error.

This module handles all three so a survey script can be about the content.

The STB1 header layout below is read out of `src/lib_util/src/classstb.cpp`
(`classSTB::Open`), which is the only place that parses it rather than seeking
past it -- `src/common/src/io/stb.cpp` treats the whole header as opaque:

    "STB1" u32 data_offset u32 raw_rows u32 raw_cols
    u32 row_height
    (raw_cols + 1) x u16 column width      <- note the +1, it is easy to miss
    raw_cols      x pstr16 column name
    raw_rows      x pstr16 row name        <- the first is the column-title line
    @data_offset: (raw_rows-1) x (raw_cols-1) x pstr16 cell

Game indices drop the header row and the root column, so `Stb.get(r, c)` is what
`get_int32(r, c)` returns on the C++ side. Column *names* are worth reading even
though nothing at runtime uses them: reference dumps label their columns and our
own files mostly do not, so a foreign header often documents a column we have but
never named.

Usage (the codecs are rosefmt's; a script reaches them with `import rosedata as oro` too):

    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "rose_data_reader", os.path.join(HERE, "rose-data-reader.py"))
    rd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rd)

    npc = rd.Stb(".../LIST_NPC.STB", "cp932")
    names = rd.stl_by_key(".../LIST_NPC_S.STL", "cp932")
    print(npc.i(1275, 7), rd.gloss(names["LNPC1275"][0]))

Run directly for a quick look at a table:

    python scripts/rose-data-reader.py <file.STB|file.STL> [--enc cp932] [--rows 20]
"""
import io
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosefmt import Stb, Stl, stl_by_key  # noqa: E402,F401

# ---------------------------------------------------------------------- STB

# ------------------------------------------------------------------- romaji

# ROSE's Japanese names are overwhelmingly katakana loanwords, so a mechanical
# transliteration usually lands back on the English original that was borrowed
# ("zeriibiin" -> Jellybean). This is for making names searchable and
# recognisable, not for translation.
_KANA = {
    'キャ': 'kya', 'キュ': 'kyu', 'キョ': 'kyo', 'シャ': 'sha', 'シュ': 'shu', 'ショ': 'sho',
    'チャ': 'cha', 'チュ': 'chu', 'チョ': 'cho', 'ニャ': 'nya', 'ニュ': 'nyu', 'ニョ': 'nyo',
    'ヒャ': 'hya', 'ヒュ': 'hyu', 'ヒョ': 'hyo', 'ミャ': 'mya', 'ミュ': 'myu', 'ミョ': 'myo',
    'リャ': 'rya', 'リュ': 'ryu', 'リョ': 'ryo', 'ギャ': 'gya', 'ギュ': 'gyu', 'ギョ': 'gyo',
    'ジャ': 'ja', 'ジュ': 'ju', 'ジョ': 'jo', 'ヂャ': 'ja', 'ヂュ': 'ju', 'ヂョ': 'jo',
    'ビャ': 'bya', 'ビュ': 'byu', 'ビョ': 'byo', 'ピャ': 'pya', 'ピュ': 'pyu', 'ピョ': 'pyo',
    'ファ': 'fa', 'フィ': 'fi', 'フェ': 'fe', 'フォ': 'fo', 'フュ': 'fyu',
    'ヴァ': 'va', 'ヴィ': 'vi', 'ヴェ': 've', 'ヴォ': 'vo', 'ヴ': 'vu',
    'ウィ': 'wi', 'ウェ': 'we', 'ウォ': 'wo', 'ティ': 'ti', 'ディ': 'di',
    'トゥ': 'tu', 'ドゥ': 'du', 'チェ': 'che', 'シェ': 'she', 'ジェ': 'je',
    'ツァ': 'tsa', 'ツィ': 'tsi', 'ツェ': 'tse', 'ツォ': 'tso',
    'デュ': 'dyu', 'テュ': 'tyu', 'クァ': 'kwa', 'クィ': 'kwi', 'クェ': 'kwe', 'クォ': 'kwo',
    'グァ': 'gwa', 'イェ': 'ye',
    'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
    'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
    'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
    'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
    'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
    'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
    'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
    'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
    'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
    'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n',
    'ガ': 'ga', 'ギ': 'gi', 'グ': 'gu', 'ゲ': 'ge', 'ゴ': 'go',
    'ザ': 'za', 'ジ': 'ji', 'ズ': 'zu', 'ゼ': 'ze', 'ゾ': 'zo',
    'ダ': 'da', 'ヂ': 'ji', 'ヅ': 'zu', 'デ': 'de', 'ド': 'do',
    'バ': 'ba', 'ビ': 'bi', 'ブ': 'bu', 'ベ': 'be', 'ボ': 'bo',
    'パ': 'pa', 'ピ': 'pi', 'プ': 'pu', 'ペ': 'pe', 'ポ': 'po',
    'ァ': 'a', 'ィ': 'i', 'ゥ': 'u', 'ェ': 'e', 'ォ': 'o',
    'ャ': 'ya', 'ュ': 'yu', 'ョ': 'yo',
    'ー': '-', '・': ' ', '　': ' ', '＝': '=',
}

# Native words that actually appear in ROSE place and item names. Longest match
# first; anything unglossed falls through to romaji.
_GLOSS = [
    ('地下監獄', 'Underground Prison'), ('訓練場', 'Training Ground'), ('冒険家', 'Adventurer'),
    ('研究所', 'Laboratory'), ('採掘場', 'Mine'), ('駐屯地', 'Garrison'),
    ('大聖堂', 'Cathedral'), ('修道院', 'Monastery'), ('貯蔵庫', 'Storehouse'),
    ('地下', 'Underground'), ('遺跡', 'Ruins'), ('神殿', 'Temple'), ('洞窟', 'Cave'),
    ('宮殿', 'Palace'), ('墓地', 'Cemetery'), ('教会', 'Church'), ('要塞', 'Fortress'),
    ('監獄', 'Prison'), ('工場', 'Factory'), ('闘技場', 'Arena'), ('競技場', 'Stadium'),
    ('植物園', 'Botanical Garden'), ('花園', 'Flower Garden'), ('楽園', 'Paradise'),
    ('草原', 'Plains'), ('砂漠', 'Desert'), ('渓谷', 'Canyon'), ('峡谷', 'Gorge'),
    ('衛星', 'Satellite'), ('前哨', 'Outpost'), ('基地', 'Base'), ('本部', 'HQ'),
    ('広場', 'Plaza'), ('入口', 'Entrance'), ('入り口', 'Entrance'),
    ('記憶', 'Memory'), ('思い出', 'Memories'), ('誕生', 'Birth'), ('封印', 'Sealed'),
    ('聖域', 'Sanctuary'), ('雪原', 'Snowfield'), ('部屋', 'Room'), ('倉庫', 'Warehouse'),
    ('市場', 'Market'), ('酒場', 'Tavern'), ('女王', 'Queen'), ('王様', 'King'),
    ('隊長', 'Captain'), ('団長', 'Commander'), ('海賊', 'Pirate'), ('盗賊', 'Bandit'),
    ('騎士', 'Knight'), ('魔法', 'Magic'), ('魔女', 'Witch'), ('戦士', 'Warrior'),
    ('弓手', 'Archer'), ('僧侶', 'Priest'), ('商人', 'Merchant'), ('見習い', 'Apprentice'),
    ('職人', 'Artisan'), ('鍛冶', 'Blacksmith'),
    ('村', 'Village'), ('町', 'Town'), ('島', 'Island'), ('谷', 'Valley'), ('丘', 'Hill'),
    ('森', 'Forest'), ('山', 'Mountain'), ('塔', 'Tower'), ('城', 'Castle'), ('海', 'Sea'),
    ('川', 'River'), ('湖', 'Lake'), ('橋', 'Bridge'), ('門', 'Gate'), ('道', 'Road'),
    ('野', 'Field'), ('原', 'Plain'), ('岩', 'Rock'), ('泉', 'Spring'), ('滝', 'Waterfall'),
    ('林', 'Woods'), ('庭', 'Garden'), ('族', 'Tribe'), ('王', 'King'), ('神', 'God'),
    ('竜', 'Dragon'), ('龍', 'Dragon'), ('獣', 'Beast'), ('鳥', 'Bird'), ('花', 'Flower'),
    ('木', 'Tree'), ('石', 'Stone'), ('氷', 'Ice'), ('炎', 'Flame'), ('火', 'Fire'),
    ('水', 'Water'), ('風', 'Wind'), ('土', 'Earth'), ('光', 'Light'), ('闇', 'Dark'),
    ('雷', 'Thunder'), ('毒', 'Poison'), ('骨', 'Bone'), ('血', 'Blood'),
    ('剣', 'Sword'), ('斧', 'Axe'), ('槍', 'Spear'), ('弓', 'Bow'), ('杖', 'Staff'),
    ('盾', 'Shield'), ('鎧', 'Armour'), ('兜', 'Helm'), ('靴', 'Boots'),
    ('手袋', 'Gloves'), ('指輪', 'Ring'), ('首飾り', 'Necklace'), ('腕輪', 'Bracelet'),
    ('宝石', 'Gem'), ('鉱石', 'Ore'), ('金', 'Gold'), ('銀', 'Silver'), ('鉄', 'Iron'),
    ('銅', 'Copper'), ('鋼', 'Steel'),
    ('北', 'North'), ('南', 'South'), ('東', 'East'), ('西', 'West'), ('中央', 'Central'),
    ('上', 'Upper'), ('下', 'Lower'), ('大', 'Great'), ('小', 'Small'),
    ('古', 'Ancient'), ('新', 'New'),
    ('赤', 'Red'), ('青', 'Blue'), ('白', 'White'), ('黒', 'Black'), ('緑', 'Green'),
    ('黄', 'Yellow'), ('の', ' of '), ('と', ' and '),
]


def romaji(s):
    """Katakana -> romaji. Leaves anything else untouched."""
    out, i, n = [], 0, len(s)
    while i < n:
        two = s[i:i + 2]
        if two in _KANA:
            out.append(_KANA[two]); i += 2; continue
        c = s[i]
        if c == 'ッ':                       # sokuon doubles the next consonant
            nxt = romaji(s[i + 1:i + 3])
            out.append(nxt[0] if nxt and nxt[0].isalpha() else '')
            i += 1; continue
        if c in _KANA:
            out.append(_KANA[c]); i += 1; continue
        out.append(c); i += 1
    r = ''.join(out)
    fixed = []                              # 'ー' repeats the previous vowel
    for ch in r:
        fixed.append(fixed[-1] if (ch == '-' and fixed and fixed[-1] in 'aiueo') else ch)
    return ''.join(fixed)


def gloss(s):
    """Readable English-ish rendering: gloss native words, romanise katakana."""
    s = (s or '').strip()
    if not s:
        return ''
    out, i = [], 0
    while i < len(s):
        for k, v in _GLOSS:
            if s.startswith(k, i):
                out.append(' ' + v + ' '); i += len(k); break
        else:
            j = i
            while j < len(s) and ('ァ' <= s[j] <= 'ヿ' or s[j] in 'ー・'):
                j += 1
            if j > i:
                out.append(romaji(s[i:j])); i = j
            else:
                out.append(s[i]); i += 1
    return ' '.join(''.join(out).split())


# Reference dumps carry Korean editor headings saved in another codepage; under
# cp932 they decode to U+FFFD and private-use noise. They hold no information,
# and some downstream consumers reject them outright, so offer a scrub.
_JUNK = re.compile("[�-\uD800-\uDFFF]")


def scrub(s):
    return re.sub(r"\s{2,}", " ", _JUNK.sub("", s or "")).strip()


# ---------------------------------------------------------------------- CLI

def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Peek at an STB or STL from any ROSE dump.")
    ap.add_argument("path")
    ap.add_argument("--enc", default="latin-1", help="cp932 for Jrose, cp949 for Korean dumps")
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--cols", type=int, default=14)
    a = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if a.path.upper().endswith(".STL"):
        t = Stl(a.path, a.enc)
        vals = t.lang()
        print("tag %s  legacy=%s  fields=%d  entries=%d  consumed %d/%d"
              % (t.tag.decode(), t.legacy, t.nfields, t.count, t.end, len(t.b)))
        for (k, i), v in list(zip(t.keys, vals))[:a.rows]:
            print("  %-10s id=%-5d %s" % (k.decode(), i, " | ".join(v)))
        return 0

    s = Stb(a.path, a.enc)
    used = sum(1 for r in range(s.rows) if s.occupied(r))
    print("%d rows x %d cols, %d occupied" % (s.rows, s.cols, used))
    kc = s.key_column()
    print("STL key column: %s" % ("none found" if kc is None else kc))
    print("columns:")
    for c in range(min(s.cols, a.cols)):
        nm = scrub(s.colname(c))
        print("  %2d  %-28s %s" % (c, nm, gloss(nm) if nm else ""))
    print("rows:")
    shown = 0
    for r in range(s.rows):
        if not s.occupied(r):
            continue
        cells = [scrub(s.s(r, c))[:18] for c in range(min(s.cols, a.cols))]
        print("  %5d  %s" % (r, " | ".join(cells)))
        shown += 1
        if shown >= a.rows:
            break
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
