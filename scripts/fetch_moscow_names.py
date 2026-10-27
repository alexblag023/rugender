"""Имена новорождённых Москвы с полом (data.mos.ru) → data_src/moscow/names.tsv.

Запускается на машине разработчика (нужен интернет), не на сервере:
    python scripts/fetch_moscow_names.py
затем пересборка: python scripts/build_data.py

Наборы «Сведения о наиболее популярных мужских / женских именах среди новорожденных»
(ЗАГС Москвы, 2015–н. в., имена с ≥3 детьми в месяц). Условия (data.mos.ru/terms):
открытые данные по ПП РФ № 583, использование без ограничений со ссылкой на Портал
открытых данных Правительства Москвы. Публичный API без ключа: описание набора
отдаёт id свежего файла (zip с JSON). В запросах нет персональных данных.
"""
from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data_src" / "moscow"
USER_AGENT = "SudKSR-rugender-data-build/1.0 (offline dictionary build; python-urllib)"
DATASETS = {"2011": "m", "2009": "f"}          # id набора на data.mos.ru → пол
META = "https://data.mos.ru/api/v2/odata/export/meta?id={id}&format=json"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def _file_url(meta: dict) -> str:
    """Ссылка на свежий файл выгрузки: описание по методике data.gov.ru v3, релизы в
    meta["data"] — первым идёт последний."""
    releases = meta.get("data") or []
    if not releases or not releases[0].get("source"):
        raise SystemExit("data.mos.ru: в описании набора нет релизов (data[].source) — формат изменился")
    return releases[0]["source"]


def main() -> None:
    counts: dict = {}
    for ds, g in DATASETS.items():
        data = _get(_file_url(json.loads(_get(META.format(id=ds)))))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            rows = json.loads(z.read(z.namelist()[0]).decode("utf-8-sig"))
        for r in rows:
            name = str(r.get("Name") or "").strip()
            if name:
                counts.setdefault(name, {"m": 0, "f": 0})[g] += int(r.get("NumberOfPersons") or 0)
        print(f"Москва {g}: строк {len(rows)}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = sorted(f"{n}\t{c['m']}\t{c['f']}" for n, c in counts.items())
    (OUT / "names.tsv").write_text(
        "# Москва, ЗАГС: популярные имена новорождённых (data.mos.ru), открытые данные со ссылкой\n"
        "# на Портал открытых данных Правительства Москвы; scripts/fetch_moscow_names.py\n"
        "# name\tmale\tfemale — сумма детей за все месяцы\n" + "\n".join(rows) + "\n",
        encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(
        f"# Москва — имена новорождённых с полом\n\nВыгружено {date.today():%d.%m.%Y} с Портала открытых "
        "данных Правительства Москвы (https://data.mos.ru), наборы 2011 (мужские имена) и 2009 (женские). "
        "Условия: https://data.mos.ru/terms — открытые данные (ПП РФ № 583 от 10.07.2013), использование "
        "без ограничений при ссылке на Портал открытых данных.\n", encoding="utf-8", newline="\n")
    print("имён:", len(rows))


if __name__ == "__main__":
    main()
