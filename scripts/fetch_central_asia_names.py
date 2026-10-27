"""Имена с полом из открытых данных Казахстана и Азербайджана →
data_src/kazakhstan/names.tsv, data_src/azerbaijan/names.tsv.

Запускается на машине разработчика (нужен интернет), не на сервере:
    python scripts/fetch_central_asia_names.py
затем пересборка: python scripts/build_data.py

Казахстан — Бюро национальной статистики, сервис «Популярные имена» (stat.gov.kz):
имя и число носителей по полу среди всего населения РК (казахи, русские, узбеки,
уйгуры, азербайджанцы, таджики, кыргызы, туркмены, каракалпаки…). Условия
(stat.gov.kz/ru/description/): свободно для любых целей, в т. ч. программных
продуктов, со ссылкой на источник. Берём имена с ≥5 носителями.
Азербайджан — Минюст, «Azərbaycan adları» (opendata.az, CC0): имена с полом,
латиница; фамилии не берём. В запросах нет персональных данных.
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data_src"
USER_AGENT = "SudKSR-rugender-data-build/1.0 (offline dictionary build; python-urllib)"
KZ_URL = ("https://stat.gov.kz/api/srn/names/populars?limit={limit}&gender={g}"
          "&dateBeg=1900-01-01&dateEnd={end}")
KZ_GENDERS = {"43036": "m", "43037": "f"}
KZ_LIMIT = 1_000_000
KZ_MIN = 5
AZ_URL = "https://exidmet.justice.gov.az:7076/Name/csv/downloadNames"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def kazakhstan() -> int:
    counts: dict = {}
    for code, g in KZ_GENDERS.items():
        rows = json.loads(_get(KZ_URL.format(limit=KZ_LIMIT, g=code, end=f"{date.today():%Y-%m-%d}")))
        if len(rows) >= KZ_LIMIT:
            raise SystemExit(f"stat.gov.kz: ответ упёрся в лимит {KZ_LIMIT} ({g}) — увеличьте KZ_LIMIT")
        print(f"Казахстан {g}: имён {len(rows)}")
        for r in rows:
            name = str(r.get("name") or "").strip()
            if re.fullmatch(r"[^\W\d_]+(-[^\W\d_]+)?", name):
                counts.setdefault(name.capitalize(), {"m": 0, "f": 0})[g] += int(r.get("count") or 0)
    rows = sorted(f"{n}\t{c['m']}\t{c['f']}" for n, c in counts.items() if c["m"] + c["f"] >= KZ_MIN)
    out = SRC / "kazakhstan"
    out.mkdir(parents=True, exist_ok=True)
    (out / "names.tsv").write_text(
        "# Казахстан, Бюро национальной статистики, «Популярные имена» (stat.gov.kz);\n"
        "# свободное использование со ссылкой на источник; scripts/fetch_central_asia_names.py\n"
        "# name\tmale\tfemale — число носителей (казахская кириллица и русская запись вперемешку)\n"
        + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (out / "README.md").write_text(
        f"# Казахстан — имена с полом\n\nВыгружено {date.today():%d.%m.%Y} из сервиса «Популярные имена» "
        "Бюро национальной статистики Агентства по стратегическому планированию и реформам РК "
        "(https://stat.gov.kz/ru/instuments/name/, API /api/srn/names/populars).\n\nУсловия использования "
        "(https://stat.gov.kz/ru/description/): данные можно использовать для любых целей, в том числе для "
        "создания программных продуктов, свободно и бесплатно, со ссылкой на источник. Изменения: имена "
        f"с ≥{KZ_MIN} носителями, суммирование по полу.\n", encoding="utf-8", newline="\n")
    return len(rows)


def azerbaijan() -> int:
    genders: dict = {}
    for line in io.StringIO(_get(AZ_URL).decode("utf-8-sig")).read().splitlines()[1:]:
        parts = line.split(",")
        # «Значение» содержит запятые без кавычек: пол — в двух последних полях.
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        name, meaning, g = parts[1], parts[2].strip().lower(), {"1": "m", "2": "f"}.get(parts[-2].strip())
        if not g or meaning.startswith("familiya"):
            continue
        for variant in name.split("//"):
            v = variant.strip()
            if re.fullmatch(r"[^\W\d_]+", v):
                genders.setdefault(v, set()).add(g)
    rows = sorted(f"{n}\t{gs.pop() if len(gs) == 1 else 'u'}" for n, gs in genders.items())
    out = SRC / "azerbaijan"
    out.mkdir(parents=True, exist_ok=True)
    (out / "names.tsv").write_text(
        "# Азербайджан, Минюст, «Azərbaycan adları» (opendata.az), CC0; scripts/fetch_central_asia_names.py\n"
        "# name\tgender (латиница; перевод в русскую запись — при сборке)\n"
        + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (out / "README.md").write_text(
        f"# Азербайджан — имена с полом\n\nВыгружено {date.today():%d.%m.%Y}: {AZ_URL}\n\nИсточник: "
        "Министерство юстиции Азербайджанской Республики, набор «Azərbaycan adları» на opendata.az. "
        "Лицензия CC0 (Creative Commons CCZero). Только личные имена (фамилии исключены).\n",
        encoding="utf-8", newline="\n")
    return len(rows)


if __name__ == "__main__":
    print("Казахстан, имён:", kazakhstan())
    print("Азербайджан, имён:", azerbaijan())
