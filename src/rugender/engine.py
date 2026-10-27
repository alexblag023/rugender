"""Определение пола по ФИО: сигналы частей ФИО и их сложение.

Сигнал — (часть ФИО, слово, правило, пол, вес). Вес положительный в сторону «ж»,
отрицательный — «м», 0 — часть есть, но пола не даёт (Ким, Петросян, Саша).
Уровни (сверху — надёжнее):
  1. отчество: окончание (-ич / -вна, -чна, -шна), частица (оглы/улы/уулу, кызы/гызы/
     кизи — отдельным словом, через дефис, слитно), вьетнамское среднее имя (Тхи / Ван)
     — решает сразу;
  2. имя: словарь (±6); у китайской/вьетнамской фамилии — слоги имени (±2 за слог),
     у корейской — слоги, если имя из нескольких слогов-слов («Джи Ын»); имя,
     разобранное на слоги, русскими окончаниями не оценивается, китайское — никогда;
     иначе морфема тюркского/иранского имени (гуль-, -бек, -жон, -иддин… ±3), иначе
     окончание имени по правилам Petrovich (±2) — у корейцев СНГ и у «Ли Анна» имена
     русские;
  3. фамилия: самое длинное окончание (±4 славянские, ±3 прибалтийские и пр.;
     -ян, -швили, -енко, -ич, -ман… — 0) или фамилия-исключение (0).
Итог по сумме весов: |S| ≥ 2 — пол по знаку, иначе «не определено» ('').
Противоречие сильных сигналов (Никита Иванова) не прячется: побеждает больший вес,
уверенность — low, оба сигнала в evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .normalize import tokens

DATA = Path(__file__).resolve().parent / "data"
SYLLABLE_GROUPS = ("chinese", "vietnamese", "korean")

W_PATRONYMIC = 10.0
W_NAME = 6.0
# Слог со склонностью к полу решает сам (= порогу): «не определено» всё равно
# превращается в мужской, и склонность слога лучше умолчания.
W_SYLLABLE = 2.0
W_MORPHEME = 3.0
W_NAME_SUFFIX = 2.0
W_SURNAME = {"slavic": 4.0}
W_SURNAME_OTHER = 3.0
DECIDE = 2.0


@dataclass(frozen=True)
class Signal:
    role: str        # surname | name | patronymic
    token: str
    rule: str        # patronymic | particle | vn_middle | name | syllables | morpheme | name_suffix | surname_suffix | surname_exact
    gender: str      # m | f | u
    weight: float
    src: str


@dataclass(frozen=True)
class Verdict:
    gender: str                 # m | f | '' (не определено)
    basis: str                  # правило решившего сигнала или none
    confidence: str             # high | medium | low | ''
    evidence: Tuple[Signal, ...]
    data_version: str


def _sign(g: str) -> float:
    return {"f": 1.0, "m": -1.0}.get(g, 0.0)


def _read(name: str) -> List[List[str]]:
    lines = (DATA / name).read_text(encoding="utf-8").splitlines()[1:]
    return [l.split("\t") for l in lines if l]


@lru_cache(maxsize=1)
def _data():
    import json
    names = {r[0]: (r[1], r[3]) for r in _read("names.tsv")}
    name_suf = {r[0]: (r[1], r[2]) for r in _read("name_suffixes.tsv")}
    sur_suf = {r[0]: (r[1], r[2], r[3]) for r in _read("surname_suffixes.tsv")}
    sur_exact = {r[0]: (r[1], set(filter(None, r[2].split(","))), r[3]) for r in _read("surname_exact.tsv")}
    syl: Dict[str, Dict[str, Tuple[str, str]]] = {}
    for r in _read("syllables.tsv"):
        syl.setdefault(r[2], {})[r[0]] = (r[1], r[3])
    patr: Dict[str, Dict[str, Tuple[str, str]]] = {}
    for r in _read("patronymic.tsv"):
        patr.setdefault(r[2], {})[r[0]] = (r[1], r[3])
    morph = [(r[0], r[2], r[1], r[3]) for r in _read("name_morphemes.tsv")]
    version = json.loads((DATA / "MANIFEST.json").read_text(encoding="utf-8"))["data_version"]
    return names, name_suf, sur_suf, sur_exact, syl, patr, morph, version


def _longest(word: str, table: Dict, min_stem: int = 1):
    """Самое длинное окончание из таблицы, короче слова хотя бы на min_stem букв."""
    for n in range(len(word) - min_stem, 0, -1):
        hit = table.get(word[-n:])
        if hit is not None:
            return word[-n:], hit
    return None, None


def _segment(word: str, syllables: Dict[str, Tuple[str, str]]) -> Optional[List[str]]:
    """Имя целиком на слоги словаря (самые длинные слоги первыми); не разобралось — None."""
    best: Dict[int, List[str]] = {0: []}
    for i in range(len(word)):
        if i not in best:
            continue
        for j in range(len(word), i, -1):
            if word[i:j] in syllables and j not in best:
                best[j] = best[i] + [word[i:j]]
    return best.get(len(word))


def _patronymic(tp: Sequence[str], tn: Sequence[str], groups: set, patr) -> List[Signal]:
    out: List[Signal] = []
    words, glued, suffixes, vn = (patr.get(k, {}) for k in ("word", "glued", "suffix", "vn_middle"))
    for t in tp:
        if t in words:
            g, src = words[t]
            out.append(Signal("patronymic", t, "particle", g, _sign(g) * W_PATRONYMIC, src))
    if not out and tp:
        last = tp[-1]
        for marker, (g, src) in glued.items():
            if last.endswith(marker) and len(last) > len(marker) + 2:
                out.append(Signal("patronymic", last, "particle", g, _sign(g) * W_PATRONYMIC, src))
                break
        else:
            suf, hit = _longest(last, suffixes, min_stem=2)
            if hit and hit[0] in "mf":
                out.append(Signal("patronymic", last, "patronymic", hit[0], _sign(hit[0]) * W_PATRONYMIC, hit[1]))
    # Вьетнамское среднее имя: «Тхи» — где угодно в имени/отчестве (русским именем не
    # бывает); «Ван» — в поле отчества, первым словом имени из нескольких слов или у
    # вьетнамской фамилии (у китайцев «Ван» — фамилия, а не признак пола).
    if not out:
        cand = list(tp) + list(tn)
        for t in cand:
            if t in vn and (t != "ван" or "vietnamese" in groups or t in tp or (len(tn) > 1 and t in tn[:-1])):
                g, src = vn[t]
                out.append(Signal("patronymic", t, "vn_middle", g, _sign(g) * W_PATRONYMIC, src))
                break
    return out


def _morpheme(t: str, morph) -> Optional[Tuple[str, str, str]]:
    """Самая длинная морфема имени (префикс/суффикс), оставляющая от имени ≥2 букв."""
    best = None
    for m, pos, g, src in morph:
        if len(t) >= len(m) + 2 and (t.startswith(m) if pos == "prefix" else t.endswith(m)):
            if best is None or len(m) > len(best[0]):
                best = (m, g, src)
    return best


def _name(tn: Sequence[str], groups: set, names, name_suf, syl, morph) -> List[Signal]:
    if not tn:
        return []
    joined = "".join(tn)
    if joined in names:
        g, src = names[joined]
        return [Signal("name", joined, "name", g, _sign(g) * W_NAME, src)]
    out: List[Signal] = []
    # Корейские слоги — только для имени из нескольких слогов-слов («Мин-хо», «Джи Ын»):
    # у корейцев СНГ имена русские, и «Анна» не должна разбираться на слоги.
    syl_groups = [g for g in SYLLABLE_GROUPS if g in groups and (g != "korean" or len(tn) > 1)]
    for t in tn:
        # Короткое слово имени-из-слогов («Джи Ын», «Сан Ук», «Тхи Хоа») — слог: в словаре
        # имён такие короткие слова — шум статистики («ын» у кого-то в паспорте).
        syllable_word = any(len(t) <= 3 and t in syl.get(g, {}) for g in syl_groups)
        if t in names and not syllable_word:
            g, src = names[t]
            out.append(Signal("name", t, "name", g, _sign(g) * W_NAME, src))
            continue
        segmented = False
        for grp in syl_groups:
            parts = _segment(t.replace("ъ", ""), syl.get(grp, {}))
            if parts:
                for p in parts:
                    g, src = syl[grp][p]
                    out.append(Signal("name", p, "syllables", g, _sign(g) * W_SYLLABLE, src))
                segmented = True
                break
        # Разобранное на слоги, китайское и многослоговое корейское имя русскими
        # окончаниями не оцениваем: «-н» у «Гуйин» — не мужской признак.
        if segmented or (groups and groups <= {"chinese"}) or ("korean" in syl_groups):
            continue
        hit = _morpheme(t, morph)
        if hit:
            out.append(Signal("name", t, "morpheme", hit[1], _sign(hit[1]) * W_MORPHEME, hit[2]))
            continue
        suf, hit = _longest(t, name_suf)
        if hit:
            out.append(Signal("name", t, "name_suffix", hit[0], _sign(hit[0]) * W_NAME_SUFFIX, hit[1]))
    return out


def _surname(ts: Sequence[str], sur_suf, sur_exact) -> List[Signal]:
    out: List[Signal] = []
    for t in ts:
        if t in sur_exact:
            g, _groups, src = sur_exact[t]
            out.append(Signal("surname", t, "surname_exact", g, _sign(g) * W_SURNAME_OTHER, src))
            continue
        suf, hit = _longest(t, sur_suf, min_stem=2)
        if hit:
            g, group, src = hit
            w = W_SURNAME.get(group, W_SURNAME_OTHER)
            out.append(Signal("surname", t, "surname_suffix", g, _sign(g) * w, src))
    return out


def split_full(ts: List[str], names) -> Tuple[List[str], List[str], List[str]]:
    """ФИО одной строкой → (фамилия, имя, отчество). Порядок по умолчанию «Ф И О»;
    первое слово — известное имя, а последнее нет — «И О Ф»."""
    if len(ts) < 2:
        return ts, [], []
    if ts[0] in names and ts[-1] not in names:
        return [ts[-1]], [ts[0]], ts[1:-1]
    return [ts[0]], [ts[1]], ts[2:]


def detect(surname=None, name=None, patronymic=None) -> Verdict:
    names, name_suf, sur_suf, sur_exact, syl, patr, morph, version = _data()
    ts, tn, tp = tokens(surname), tokens(name), tokens(patronymic)
    filled = [x for x in (ts, tn, tp) if x]
    if len(filled) == 1 and len(filled[0]) > 1 and not tn:
        ts, tn, tp = split_full(filled[0], names)
    groups = set().union(*(sur_exact[t][1] for t in ts if t in sur_exact)) if ts else set()

    signals = _patronymic(tp, tn, groups, patr)
    if signals:
        s = signals[0]
        return Verdict(s.gender, s.rule, "high", tuple(signals), version)
    # У вьетнамцев поле отчества часто содержит среднее имя или само имя («Ле | Ань | Нгок»).
    name_tokens = list(tn) + list(tp) if "vietnamese" in groups else (tn or tp)
    signals = _name(name_tokens, groups, names, name_suf, syl, morph) + _surname(ts, sur_suf, sur_exact)
    total = sum(s.weight for s in signals)
    if abs(total) < DECIDE:
        return Verdict("", "none", "", tuple(signals), version)
    gender = "f" if total > 0 else "m"
    agree = [s for s in signals if s.weight * total > 0]
    basis = max(agree, key=lambda s: abs(s.weight)).rule
    conflict = any(s.weight * total < 0 and abs(s.weight) >= W_SURNAME_OTHER for s in signals)
    conf = "low" if conflict or abs(total) < 4 else ("high" if abs(total) >= 6 else "medium")
    return Verdict(gender, basis, conf, tuple(signals), version)
