"""Качество rugender на эталонном корпусе (tests/corpus.tsv) по группам ФИО.

    python scripts/evaluate.py            # таблица
    python scripts/evaluate.py --errors   # + ошибки и «не определено»
    python scripts/evaluate.py --pytrovich  # + сравнение с pytrovich

Метрики группы: n — ФИО; acc — точность на решённых; undet — доля «не определено»
(уйдёт в пол по умолчанию — мужской); final — точность после умолчания; f→m — доля
женщин, получивших «м» (главный риск умолчания).
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "corpus.tsv"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rugender import detect  # noqa: E402

DEFAULT = "m"


def load(path: Path = CORPUS) -> List[Dict[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = (line.split("\t") + [""] * 6)[:6]
        rows.append(dict(zip(("group", "surname", "name", "patronymic", "gold", "note"), f)))
    return rows


def evaluate(rows, fn: Callable[[str, str, str], str]) -> Dict[str, Dict]:
    stat: Dict[str, Dict] = defaultdict(lambda: {"n": 0, "dec": 0, "ok": 0, "undet": 0, "final": 0,
                                                 "f": 0, "f2m": 0, "errors": [], "unknown": []})
    for r in rows:
        g = fn(r["surname"], r["name"], r["patronymic"])
        for key in (r["group"], "ВСЕГО"):
            s = stat[key]
            s["n"] += 1
            s["f"] += r["gold"] == "f"
            if g:
                s["dec"] += 1
                s["ok"] += g == r["gold"]
                if g != r["gold"] and key != "ВСЕГО":
                    s["errors"].append(r)
            else:
                s["undet"] += 1
                if key != "ВСЕГО":
                    s["unknown"].append(r)
            final = g or DEFAULT
            s["final"] += final == r["gold"]
            s["f2m"] += r["gold"] == "f" and final == "m"
    for s in stat.values():
        s["acc"] = s["ok"] / s["dec"] if s["dec"] else 1.0
        s["undet_rate"] = s["undet"] / s["n"]
        s["final_acc"] = s["final"] / s["n"]
        s["f2m_rate"] = s["f2m"] / s["f"] if s["f"] else 0.0
    return dict(stat)


def holdout(rows):
    """ФИО, имя которых не найдено в словаре имён (корпус и словари составлял один
    автор — на словарных именах точность завышена)."""
    from rugender.engine import _data
    from rugender.normalize import tokens
    names = _data()[0]
    return [r for r in rows if not (set(tokens(r["name"])) | {"".join(tokens(r["name"]))}) & set(names)]


def rugender_fn(surname, name, patronymic) -> str:
    return detect(surname or None, name or None, patronymic or None).gender


def pytrovich_fn(surname, name, patronymic) -> str:
    from pytrovich.detector import PetrovichGenderDetector
    from pytrovich.enums import Gender
    parts = {"lastname": surname or None, "firstname": name or None, "middlename": patronymic or None}
    if not any(parts.values()):
        return ""
    try:
        return {Gender.MALE: "m", Gender.FEMALE: "f"}.get(PetrovichGenderDetector().detect(**parts), "")
    except Exception:  # noqa: BLE001
        return ""


def table(stat, title):
    print(f"\n{title}")
    print(f"{'группа':<18}{'n':>5}{'acc':>8}{'undet':>8}{'final':>8}{'f→m':>8}")
    for k in sorted(stat, key=lambda k: (k == "ВСЕГО", k)):
        s = stat[k]
        print(f"{k:<18}{s['n']:>5}{s['acc']:>8.1%}{s['undet_rate']:>8.1%}{s['final_acc']:>8.1%}{s['f2m_rate']:>8.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--pytrovich", action="store_true")
    ap.add_argument("--holdout", action="store_true",
                    help="только ФИО, чьего имени нет в словаре: честная оценка правил на незнакомом")
    ap.add_argument("--corpus", type=Path, default=CORPUS,
                    help="другой корпус, напр. tests/corpus_blind.tsv (слепой, независимый автор)")
    args = ap.parse_args()
    rows = load(args.corpus)
    if args.holdout:
        rows = holdout(rows)
    stat = evaluate(rows, rugender_fn)
    table(stat, "rugender")
    if args.errors:
        for k in sorted(stat):
            for r in stat[k]["errors"]:
                v = detect(r["surname"] or None, r["name"] or None, r["patronymic"] or None)
                print(f"  ✗ {k}: {r['surname']} {r['name']} {r['patronymic']} — ждали {r['gold']}, "
                      f"получили {v.gender} ({v.basis}; {[(s.token, s.rule, s.weight) for s in v.evidence]})")
            for r in stat[k]["unknown"]:
                print(f"  ? {k}: {r['surname']} {r['name']} {r['patronymic']} — ждали {r['gold']}")
    if args.pytrovich:
        try:
            import pytrovich  # noqa: F401 — в зависимостях проекта его нет: только для сравнения
        except ImportError:
            print("\npytrovich не установлен (pip install pytrovich==0.2.0) — сравнение пропущено")
        else:
            table(evaluate(rows, pytrovich_fn), "pytrovich 0.2.0 (для сравнения)")


if __name__ == "__main__":
    main()
