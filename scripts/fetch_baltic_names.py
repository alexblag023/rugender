"""Имена с полом из открытых данных Латвии (CC0) и Литвы (CC BY 4.0) →
data_src/latvia/names.tsv, data_src/lithuania/names.tsv.

Запускается на машине разработчика (нужен интернет), не на сервере:
    python scripts/fetch_baltic_names.py
затем пересборка: python scripts/build_data.py (перевод в русскую запись —
scripts/translit.py, при сборке).

Латвия — PMLP «Personu vārdi» (data.gov.lv, CC0 1.0): имя, пол, число носителей;
берём однословные имена с ≥3 носителями (меньше — опечатки и редкости).
Литва — VLKK «Vardų lingvistiniai duomenys» (data.gov.lt #2664, CC BY 4.0): словарь
имён с полом; однословные. В запросах нет персональных данных.
"""
from __future__ import annotations

import csv
import io
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data_src"
USER_AGENT = "SudKSR-rugender-data-build/1.0 (offline dictionary build; python-urllib)"
LV_URL = ("https://data.gov.lv/dati/dataset/ac246d11-d5d6-445e-a6c7-8f5013460335/resource/"
          "10f0bb84-dd18-44e9-9a80-dc1515a4b3a9/download/vardi-dz-20260701.csv")
LT_URL = "https://data.gov.lt/datasets/2664/versions/813/dynamic-resource/Vardas/csv/download/"
LV_MIN = 3
_ONE = re.compile(r"^[^\W\d_]+(-[^\W\d_]+)?$")


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8-sig")


def _write(path: Path, header: str, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(sorted(rows)) + "\n", encoding="utf-8", newline="\n")


def latvia() -> int:
    counts: dict = {}
    for r in csv.DictReader(io.StringIO(_get(LV_URL))):
        name = (r.get("Vardi") or "").strip()
        g = {"VĪRIETIS": "m", "SIEVIETE": "f"}.get((r.get("Dzimums") or "").strip())
        if g and _ONE.match(name):
            counts.setdefault(name.capitalize(), {"m": 0, "f": 0})[g] += int(r.get("Skaits") or 0)
    rows = [f"{n}\t{c['m']}\t{c['f']}" for n, c in counts.items() if c["m"] + c["f"] >= LV_MIN]
    _write(SRC / "latvia" / "names.tsv",
           "# Латвия, PMLP «Personu vārdi» (data.gov.lv), CC0 1.0; scripts/fetch_baltic_names.py\n"
           "# name\tmale\tfemale — число носителей\n", rows)
    (SRC / "latvia" / "README.md").write_text(
        f"# Латвия — имена с полом\n\nВыгружено {date.today():%d.%m.%Y}: {LV_URL}\n\n"
        "Источник — Управление по делам гражданства и миграции Латвии (PMLP), набор «Personu vārdi» "
        "на data.gov.lv. Лицензия CC0 1.0. Однословные имена с ≥3 носителями.\n", encoding="utf-8", newline="\n")
    return len(rows)


def lithuania() -> int:
    genders: dict = {}
    for r in csv.DictReader(io.StringIO(_get(LT_URL))):
        name = (r.get("pilnas_vardas") or "").strip()
        g = {"Vyras": "m", "Moteris": "f"}.get((r.get("lytis") or "").strip())
        if g and _ONE.match(name):
            genders.setdefault(name, set()).add(g)
    rows = [f"{n}\t{gs.pop() if len(gs) == 1 else 'u'}" for n, gs in genders.items()]
    _write(SRC / "lithuania" / "names.tsv",
           "# Литва, VLKK «Vardų lingvistiniai duomenys» (data.gov.lt #2664), CC BY 4.0;\n"
           "# scripts/fetch_baltic_names.py\n# name\tgender\n", rows)
    (SRC / "lithuania" / "README.md").write_text(
        f"# Литва — имена с полом\n\nВыгружено {date.today():%d.%m.%Y}: {LT_URL}\n\n"
        "Источник: Valstybinė lietuvių kalbos komisija (VLKK), набор «Vardų lingvistiniai duomenys», "
        "data.gov.lt (#2664). Лицензия Creative Commons Attribution 4.0 "
        "(https://creativecommons.org/licenses/by/4.0/) — атрибуция обязательна (указана здесь и в "
        "src/rugender/data/MANIFEST.json). Изменения: однословные имена, пол, перевод в русскую запись.\n",
        encoding="utf-8", newline="\n")
    return len(rows)


if __name__ == "__main__":
    print("Латвия, имён:", latvia())
    print("Литва, имён:", lithuania())
