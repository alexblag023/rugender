"""Частоты пола по личным именам людей бывшего СССР из Wikidata (CC0) →
data_src/wikidata_people/given_names.tsv.

Запускается на машине разработчика (нужен интернет), не на сервере:
    python scripts/fetch_wikidata_people_names.py
затем пересборка: python scripts/build_data.py

Для каждой страны (СССР, Российская империя, 15 республик) и пола (P21) считаем
людей (Q5) с личным именем (P735), у которого есть русская метка: «Айгерим — ж 41,
м 0». Это реальная статистика употребления имени, а не класс «мужское/женское
имя». Запрос, не уложившийся в лимит WDQS, делится по годам рождения.
Промежуточные ответы кешируются (повторный запуск не повторяет запросы).
В запросах нет персональных данных: служебный User-Agent без контактов.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data_src" / "wikidata_people"
CACHE = OUT / ".cache"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "SudKSR-rugender-data-build/1.0 (offline dictionary build; python-urllib)"
PAUSE_SEC = 65          # WDQS при нагрузке — 1 запрос в минуту
COUNTRIES = {
    "Q15180": "СССР", "Q34266": "Российская империя", "Q159": "Россия", "Q212": "Украина",
    "Q184": "Беларусь", "Q217": "Молдова", "Q37": "Литва", "Q211": "Латвия", "Q191": "Эстония",
    "Q230": "Грузия", "Q399": "Армения", "Q227": "Азербайджан", "Q232": "Казахстан",
    "Q265": "Узбекистан", "Q813": "Киргизия", "Q863": "Таджикистан", "Q874": "Туркмения",
}
SEXES = {"Q6581097": "m", "Q6581072": "f"}
SPLITS = [(None, 1900), (1900, 1940), (1940, 1970), (1970, None)]
_WORD = re.compile(r"^[А-ЯЁ][а-яё]+(-[А-ЯЁа-яё][а-яё]+)?$")


class Timeout(Exception):
    pass


def _sparql(q: str) -> list:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/sparql-results+json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 504) and attempt >= 1:
                raise Timeout(str(e)) from e
            wait = PAUSE_SEC * (attempt + 1)
        except (TimeoutError, urllib.error.URLError, ValueError) as e:
            # ValueError — битый JSON: WDQS под нагрузкой обрывает большой ответ.
            if attempt >= 1:
                raise Timeout(str(e)) from e
            wait = PAUSE_SEC
        print(f"    повтор через {wait} с", file=sys.stderr)
        time.sleep(wait)
    raise Timeout("нет ответа")


def _query(country: str, sex: str, years) -> dict:
    flt = ""
    if years != (None, None):
        lo, hi = years
        flt = "?p wdt:P569 ?b . " + " ".join(
            x for x in (f"FILTER(YEAR(?b) >= {lo})" if lo else "", f"FILTER(YEAR(?b) < {hi})" if hi else "") if x)
    q = (f"SELECT ?label (COUNT(?p) AS ?c) WHERE {{ ?p wdt:P27 wd:{country} ; wdt:P21 wd:{sex} ; "
         f"wdt:P735 ?n . {flt} ?n rdfs:label ?label . FILTER(LANG(?label) = \"ru\") }} GROUP BY ?label")
    key = CACHE / f"{country}_{sex}_{years[0]}_{years[1]}.json"
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    rows = _sparql(q)
    res = {b["label"]["value"]: int(b["c"]["value"]) for b in rows}
    CACHE.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    time.sleep(PAUSE_SEC)
    return res


def main() -> None:
    counts: dict = {}
    for country, cname in COUNTRIES.items():
        for sex, g in SEXES.items():
            parts = [(None, None)]
            try:
                got = [_query(country, sex, (None, None))]
            except Timeout:
                print(f"  {cname} {g}: таймаут целиком — делю по годам рождения", file=sys.stderr)
                got, parts = [], SPLITS
                for years in SPLITS:
                    try:
                        got.append(_query(country, sex, years))
                    except Timeout:
                        print(f"  {cname} {g} {years}: таймаут — пропущено", file=sys.stderr)
            n = 0
            for res in got:
                for label, c in res.items():
                    if _WORD.match(label.strip()):
                        counts.setdefault(label.strip(), {"m": 0, "f": 0})[g] += c
                        n += c
            print(f"{cname} {g}: людей с именем {n} (частей запроса {len(parts)})")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = sorted(f"{name}\t{c['m']}\t{c['f']}" for name, c in counts.items())
    (OUT / "given_names.tsv").write_text(
        "# Личные имена людей бывшего СССР из Wikidata (CC0): сколько людей с этим именем\n"
        "# мужчин и женщин; scripts/fetch_wikidata_people_names.py\n# name\tmale\tfemale\n"
        + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(
        f"# Wikidata — частоты пола по личным именам людей бывшего СССР\n\nВыгружено "
        f"{date.today():%d.%m.%Y} скриптом `scripts/fetch_wikidata_people_names.py`: люди (Q5) с "
        "гражданством (P27) СССР, Российской империи и 15 республик, пол (P21), личное имя (P735) с "
        "русской меткой. Лицензия данных Wikidata — CC0 1.0. Данные — о именах (частоты), не о людях.\n",
        encoding="utf-8", newline="\n")
    print("имён:", len(rows))


if __name__ == "__main__":
    main()
