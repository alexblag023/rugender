"""Выгрузка имён с полом из Wikidata (CC0) в data_src/wikidata/names.tsv.

Запускается на машине разработчика (нужен интернет), не на сервере:
    python scripts/fetch_wikidata_names.py
затем пересборка данных: python scripts/build_data.py

Пол имени в Wikidata — класс элемента: Q12308941 мужское имя, Q11879590 женское,
Q3409032 унисекс. Берём русскую метку (rdfs:label@ru): одно слово кириллицей
(допускается дефис). Имя в нескольких классах — u. Результат отсортирован —
повторная выгрузка даёт diff только по реальным изменениям Wikidata.
В запросах нет персональных данных: служебный User-Agent без контактов.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data_src" / "wikidata"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "SudKSR-rugender-data-build/1.0 (offline dictionary build; python-urllib)"
CLASSES = {"Q12308941": "m", "Q11879590": "f", "Q3409032": "u"}
# Запрос на класс и первую букву метки: большие ответы WDQS под нагрузкой обрывает
# на середине (битый JSON). Ответы кешируются — повторный запуск продолжает с места.
LETTERS = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЭЮЯ"
PAUSE_SEC = 65          # WDQS при нагрузке ограничивает до 1 запроса в минуту
CACHE = OUT / ".cache"
_WORD = re.compile(r"^[А-ЯЁа-яё]+(-[А-ЯЁа-яё]+)?$")


def _query(cls: str, letter: str) -> list:
    key = CACHE / f"{cls}_{letter}.json"
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    q = (f'SELECT ?label WHERE {{ ?item wdt:P31 wd:{cls} . ?item rdfs:label ?label . '
         f'FILTER(LANG(?label) = "ru") FILTER(STRSTARTS(?label, "{letter}")) }}')
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                labels = [b["label"]["value"] for b in json.load(r)["results"]["bindings"]]
            CACHE.mkdir(parents=True, exist_ok=True)
            key.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
            time.sleep(PAUSE_SEC)                   # вежливость к общему сервису
            return labels
        except Exception as e:  # noqa: BLE001 — сеть/таймаут Wikidata: повтор с паузой
            print(f"  {cls} {letter}: {e} — повтор {attempt + 1}", file=sys.stderr)
            time.sleep(PAUSE_SEC * (attempt + 1))
    raise SystemExit(f"Wikidata не ответила: {cls} {letter}")


def main() -> None:
    genders: dict = {}
    for cls, g in CLASSES.items():
        got = 0
        for letter in LETTERS:
            labels = _query(cls, letter)
            for lab in labels:
                lab = lab.strip()
                if _WORD.match(lab):
                    genders.setdefault(lab, set()).add(g)
            got += len(labels)
        print(f"{cls} ({g}): {got}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = sorted(f"{name}\t{gs.pop() if len(gs) == 1 else 'u'}" for name, gs in genders.items())
    (OUT / "names.tsv").write_text(
        "# Имена с полом из Wikidata (CC0), русские метки; scripts/fetch_wikidata_names.py\n"
        "# name\tgender\n" + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(
        f"# Wikidata — имена с полом\n\nВыгружено {date.today():%d.%m.%Y} скриптом "
        "`scripts/fetch_wikidata_names.py` с query.wikidata.org: элементы классов Q12308941 "
        "(мужское имя), Q11879590 (женское), Q3409032 (унисекс) с русской меткой.\n\n"
        "Лицензия данных Wikidata — CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/), "
        "атрибуция не обязательна, указываем источник для прозрачности.\n", encoding="utf-8", newline="\n")
    print("записано имён:", len(rows))


if __name__ == "__main__":
    main()
