"""Татарско-русский словарь личных имён ЗАГС Татарстана (CC BY 4.0) →
data_src/tatarstan/names.tsv (имя в русской записи, пол, имя по-татарски).

Два шага (сервер в интернет не ходит, а pypdf есть только в образе):
    python scripts/fetch_tatarstan_names.py --download          # хост: PDF → .cache/
    python scripts/fetch_tatarstan_names.py --parse
затем пересборка: python scripts/build_data.py

Строки PDF: «мужской  Абелькадыр  Әбелкадыйр  Абелькадырович  Әбелкадыйр улы …»,
«женский  Агдалия  Әгъдәлия». Атрибуция — в README.md и MANIFEST.json данных.
"""
from __future__ import annotations

import argparse
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data_src" / "tatarstan"
CACHE = OUT / ".cache"
PAGE = "https://zags.tatarstan.ru/rus/tatarsko-russkiy-slovar-lichnih-imen-otchestv-i.htm"
PDF_URL = "https://zags.tatarstan.ru/file/zags/File/" + urllib.parse.quote("Имена и отчества.pdf")
USER_AGENT = "SudKSR-rugender-data-build/1.0 (offline dictionary build; python-urllib)"
_ROW = re.compile(r"^(мужской|женский)\s+([А-ЯЁ][а-яё]+(?:-[А-ЯЁа-яё][а-яё]+)?)\s+(\S+)")


def download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(PDF_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r:
        (CACHE / "names.pdf").write_bytes(r.read())
    print("скачано:", (CACHE / "names.pdf").stat().st_size, "байт")


def parse() -> None:
    from pypdf import PdfReader
    text = "\n".join(page.extract_text(extraction_mode="layout") or ""
                     for page in PdfReader(str(CACHE / "names.pdf")).pages)
    genders: dict = {}
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if m:
            g = "m" if m.group(1) == "мужской" else "f"
            genders.setdefault(m.group(2), (set(), m.group(3)))[0].add(g)
    rows = sorted(f"{n}\t{gs.pop() if len(gs) == 1 else 'u'}\t{tt}" for n, (gs, tt) in genders.items())
    (OUT / "names.tsv").write_text(
        "# ЗАГС Республики Татарстан, «Татарско-русский словарь личных имён, отчеств и фамилий»,\n"
        "# CC BY 4.0; scripts/fetch_tatarstan_names.py\n# name\tgender\tname_tt\n"
        + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (OUT / "README.md").write_text(
        f"# Татарстан — имена с полом\n\nВыгружено {date.today():%d.%m.%Y} со страницы {PAGE} "
        "(файл «Имена и отчества.pdf»).\n\nИсточник: Управление ЗАГС Кабинета Министров Республики "
        "Татарстан, «Татарско-русский словарь личных имён, отчеств и фамилий». Материалы сайта — "
        "Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/), "
        "атрибуция обязательна (указана здесь и в src/rugender/data/MANIFEST.json). Изменения: "
        "извлечены имя в русской записи, пол и татарская запись.\n", encoding="utf-8", newline="\n")
    print("имён:", len(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--parse", action="store_true")
    a = ap.parse_args()
    if a.download:
        download()
    if a.parse:
        parse()
