"""Сборка данных rugender: data_src/* → src/rugender/data/*.tsv + MANIFEST.json.

Данные пакета руками не правят — только источники в data_src/ и пересборка:
    python scripts/build_data.py           # собрать
    python scripts/build_data.py --check   # данные пакета совпадают со сборкой (тест)

Сборка детерминирована (сортировка, LF, без меток времени): повторный запуск даёт
те же байты. У каждой строки — источник (`src`): для атрибуции и объяснимости.
Приоритет источников при расхождении: manual > petrovich. Внутри manual имя с
разным полом в разных группах становится u.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data_src"
OUT = ROOT / "src" / "rugender" / "data"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from rugender.normalize import norm_word  # noqa: E402
from translit import az_to_ru, lt_to_ru, lv_to_ru  # noqa: E402

DATA_VERSION = "2026.10.1"
SOURCES = {
    "petrovich": {"path": "data_src/petrovich", "license": "MIT",
                  "copyright": "Copyright (c) 2013 Petrovich Developers",
                  "url": "https://github.com/petrovich/petrovich-rules"},
    "manual": {"path": "data_src/manual", "license": "MIT",
               "copyright": "rugender contributors", "url": "https://github.com/alexblag023/rugender"},
    "wikidata_people": {"path": "data_src/wikidata_people", "license": "CC0-1.0",
                        "copyright": "Wikidata", "url": "https://query.wikidata.org"},
    "wikidata": {"path": "data_src/wikidata", "license": "CC0-1.0",
                 "copyright": "Wikidata", "url": "https://query.wikidata.org"},
    "latvia": {"path": "data_src/latvia", "license": "CC0-1.0",
               "copyright": "PMLP (Латвия), «Personu vārdi»", "url": "https://data.gov.lv/dati/dataset/personu-vardi"},
    "tatarstan": {"path": "data_src/tatarstan", "license": "CC-BY-4.0",
                  "copyright": "Управление ЗАГС Кабинета Министров Республики Татарстан, «Татарско-русский "
                               "словарь личных имён, отчеств и фамилий»",
                  "url": "https://zags.tatarstan.ru/rus/tatarsko-russkiy-slovar-lichnih-imen-otchestv-i.htm"},
    "moscow": {"path": "data_src/moscow",
               "license": "открытые данные (ПП РФ № 583), использование со ссылкой на Портал открытых данных",
               "copyright": "Управление ЗАГС города Москвы, Портал открытых данных Правительства Москвы",
               "url": "https://data.mos.ru/terms"},
    "kazakhstan": {"path": "data_src/kazakhstan",
                   "license": "свободное использование со ссылкой на источник (stat.gov.kz/ru/description/)",
                   "copyright": "Бюро национальной статистики АСПиР РК, сервис «Популярные имена»",
                   "url": "https://stat.gov.kz/ru/instuments/name/"},
    "azerbaijan": {"path": "data_src/azerbaijan", "license": "CC0-1.0",
                   "copyright": "Министерство юстиции Азербайджанской Республики, «Azərbaycan adları»",
                   "url": "https://opendata.az/en/@azerbaycan-respublikasi-edliyye-nazirliyi/azerbaycan-adlari"},
    "lithuania": {"path": "data_src/lithuania", "license": "CC-BY-4.0",
                  "copyright": "Valstybinė lietuvių kalbos komisija (VLKK), «Vardų lingvistiniai duomenys»",
                  "url": "https://data.gov.lt/datasets/2664/"},
}
# Порядок доверия словарям имён: первый источник, знающий имя, решает; расхождения
# следующих печатаются при сборке (для ревизии), но не перекрывают.
# Исключения Petrovich составлены для склонения, а не для пола (там «Сигитас» — ж,
# «Свитлана» — м), поэтому статистика носителей имён надёжнее и стоит выше.
# Источники данных о реальном употреблении (статистика, официальные словари): их
# расхождение между собой — признак двуполого имени.
DATA_SOURCES = {"tatarstan", "moscow", "kazakhstan", "wikidata_people", "latvia", "lithuania", "azerbaijan"}
NAME_PRIORITY = ("manual", "tatarstan", "moscow", "kazakhstan", "wikidata_people", "latvia", "lithuania", "azerbaijan",
                 "petrovich", "wikidata", "latvia_short")
_G = {"male": "m", "female": "f", "androgynous": "u"}


class BuildError(Exception):
    pass


def _key(word: str, where: str) -> str:
    """Ключ словаря; латиница — ошибка источника. Однобуквенные слова (кит. «Ю», «У»)
    дают '': во входе они неотличимы от инициалов и отбрасываются нормализацией."""
    if re.search(r"[A-Za-z]", word):
        raise BuildError(f"{where}: латиница в «{word}»")
    if len(word.replace("-", "")) <= 1:
        return ""
    k = norm_word(word.replace("-", ""))
    if not k:
        raise BuildError(f"{where}: пустое слово «{word}»")
    return k


def _suffix(s: str, where: str) -> str:
    """Окончание/частица → ключ: однобуквенные окончания («л», «к») значимы — в отличие
    от слов, инициалом они не бывают."""
    k = s.strip().lower().replace("ё", "е")
    if not re.fullmatch(r"[а-я]+", k):
        raise BuildError(f"{where}: окончание «{s}» не из русских букв")
    return k


def _sections(path: Path) -> Iterable[Tuple[str, str, List[str]]]:
    """[группа] + «m: …» строки → (группа, пол, слова). Слова с «?» — не проверены, пропускаются."""
    group = ""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"\[(\w+)\]", line)
        if m:
            group = m.group(1)
            continue
        m = re.fullmatch(r"([mfu]):\s*(.*)", line)
        if m:
            yield group, m.group(1), [w for w in m.group(2).split() if "?" not in w]
        elif group:
            yield group, "u", [w for w in line.split() if "?" not in w]   # surnames_exact: без пола
        else:
            raise BuildError(f"{path.name}:{n}: строка вне группы")


def _tsv(path: Path) -> Iterable[List[str]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            yield line.split("\t")


REPORT: Dict[str, object] = {}


def _by_counts(m: int, f: int, min_n: int, share: float = 0.95) -> str:
    """Пол имени по числу носителей: явное большинство — пол; заметно у обоих — u; мало — ''."""
    n = m + f
    if n < min_n:
        return ""
    if max(m, f) / n >= share:
        return "m" if m > f else "f"
    return "u" if n >= 10 * min_n and min(m, f) / n >= 0.2 else ""


def _open_name_layers() -> Dict[str, Dict[str, Tuple[str, set]]]:
    """Словари из открытых данных (если выгружены): Wikidata, Латвия, Литва."""
    out: Dict[str, Dict[str, Tuple[str, set]]] = {}

    def add(src: str, word: str, g: str) -> None:
        k = norm_word(word.replace("-", ""))
        # Имена из 1–2 букв в статистике — опечатки и обрывки («Ын», «Ли»), не имена.
        if g and k and len(k) > 2 and re.fullmatch(r"[а-я]+", k):
            out.setdefault(src, {}).setdefault(k, (g, {src}))

    p = SRC / "wikidata_people" / "given_names.tsv"
    if p.exists():
        for r in _tsv(p):
            add("wikidata_people", r[0], _by_counts(int(r[1]), int(r[2]), min_n=3))
    p = SRC / "moscow" / "names.tsv"
    if p.exists():
        for r in _tsv(p):
            add("moscow", r[0], _by_counts(int(r[1]), int(r[2]), min_n=3))
    p = SRC / "kazakhstan" / "names.tsv"
    if p.exists():
        # Казахская кириллица (Әйгерім) сводится к русской записи нормализацией norm_word.
        for r in _tsv(p):
            add("kazakhstan", r[0], _by_counts(int(r[1]), int(r[2]), min_n=5))
    p = SRC / "azerbaijan" / "names.tsv"
    if p.exists():
        for r in _tsv(p):
            for v in az_to_ru(r[0]):
                add("azerbaijan", v, r[1])
    p = SRC / "tatarstan" / "names.tsv"
    if p.exists():
        for r in _tsv(p):
            add("tatarstan", r[0], r[1])
    p = SRC / "wikidata" / "names.tsv"
    if p.exists():
        for r in _tsv(p):
            add("wikidata", r[0], r[1])
    p = SRC / "latvia" / "names.tsv"
    if p.exists():
        for r in _tsv(p):
            g = _by_counts(int(r[1]), int(r[2]), min_n=3)
            if not g or not re.fullmatch(r"[a-zāčēģīķļņšūž]+", r[0].lower()):
                continue                       # буквы вне латышского алфавита — заимствования, пропуск
            variants = lv_to_ru(r[0], male=g == "m")
            add("latvia", variants[0], g)
            for v in variants[1:]:
                add("latvia_short", v, g)
    p = SRC / "lithuania" / "names.tsv"
    if p.exists():
        for r in _tsv(p):
            if re.fullmatch(r"[a-ząčęėįšųūž]+", r[0].lower()):
                add("lithuania", lt_to_ru(r[0])[0], r[1])
    return out


def build() -> Dict[str, str]:
    petr = json.loads((SRC / "petrovich" / "gender.json").read_text(encoding="utf-8"))["gender"]
    man = SRC / "manual"

    # --- имена: слои источников (src → {name: (g, groups)}), затем слияние по NAME_PRIORITY
    layers: Dict[str, Dict[str, Tuple[str, set]]] = {"petrovich": {}, "manual": {}}
    for g_en, words in (petr["firstname"].get("exceptions") or {}).items():
        for w in words:
            layers["petrovich"][_key(w, "petrovich")] = (_G[g_en], {"petrovich"})
    manual_names: Dict[str, Tuple[set, set]] = {}
    for group, g, words in _sections(man / "names.txt"):
        for w in filter(lambda w: _key(w, f"names.txt[{group}]"), words):
            gs, groups = manual_names.setdefault(_key(w, f"names.txt[{group}]"), (set(), set()))
            gs.add(g)
            groups.add(group)
    for k, (gs, groups) in manual_names.items():
        layers["manual"][k] = (gs.pop() if len(gs) == 1 else "u", groups)
    layers.update(_open_name_layers())
    names: Dict[str, Tuple[str, set, str]] = {}
    conflicts: Dict[Tuple[str, str], List[str]] = {}
    for src in NAME_PRIORITY:
        for k, (g, groups) in sorted(layers.get(src, {}).items()):
            if k in names:
                prev_g, prev_groups, prev_src = names[k]
                if prev_g != g:
                    conflicts.setdefault((prev_src, src), []).append(f"{k} {prev_g}≠{g}")
                    # Два независимых источника данных называют разный пол — имя у разных
                    # народов разное (Айман: каз. ж, тат. м): u, решают отчество и фамилия.
                    if prev_src in DATA_SOURCES and src in DATA_SOURCES and {prev_g, g} == {"m", "f"}:
                        names[k] = ("u", prev_groups | groups, prev_src)
                continue
            names[k] = (g, groups, src)
    REPORT["names_by_src"] = {src: sum(1 for v in names.values() if v[2] == src) for src in NAME_PRIORITY}
    REPORT["conflicts"] = {f"{a}>{b}": v for (a, b), v in sorted(conflicts.items())}

    # --- окончания имён (Petrovich): самое длинное решает
    name_suf = {_suffix(s, "petrovich"): (_G[g_en], "petrovich")
                for g_en, sufs in (petr["firstname"].get("suffixes") or {}).items() for s in sufs}

    # --- фамилии: окончания и точные
    sur_suf: Dict[str, Tuple[str, str, str]] = {}
    for g_en, sufs in petr["lastname"]["suffixes"].items():
        for s in sufs:
            sur_suf[_suffix(s, "petrovich")] = (_G[g_en], "slavic", "petrovich")
    for row in _tsv(man / "surname_suffixes.tsv"):
        sur_suf[_suffix(row[0], "surname_suffixes.tsv")] = (row[1], row[2], "manual")
    sur_exact: Dict[str, Tuple[str, str, str]] = {}
    for g_en, words in (petr["lastname"].get("exceptions") or {}).items():
        for w in words:
            sur_exact[_key(w, "petrovich")] = (_G[g_en], "", "petrovich")
    for group, _g, words in _sections(man / "surnames_exact.txt"):
        for w in words:
            k = _key(w, f"surnames_exact.txt[{group}]")
            if not k:
                continue
            prev = sur_exact.get(k)
            # Одна фамилия у нескольких групп (Ли — кит. и кор.): группы через запятую.
            groups = sorted(set((prev[1].split(",") if prev and prev[2] == "manual" else []) + [group]))
            sur_exact[k] = ("u", ",".join(groups), "manual")

    # --- слоги китайских, вьетнамских, корейских имён
    syl: Dict[Tuple[str, str], Tuple[str, str]] = {}
    seen: Dict[Tuple[str, str], set] = {}
    for group, g, words in _sections(man / "syllables.txt"):
        for w in words:
            # Слоги бывают однобуквенными («а», «е», «я») — нормализация окончаний.
            seen.setdefault((_suffix(w, f"syllables.txt[{group}]"), group), set()).add(g)
    for (k, group), gs in seen.items():
        # Слог из полного (нейтрального) набора со склонностью к полу — берём
        # склонность; склонность к обоим полам — u.
        gendered = gs - {"u"}
        syl[(k, group)] = (gendered.pop() if len(gendered) == 1 else "u", "manual")

    # --- морфемы имён (тюркские, иранские, арабские)
    morph = {(_suffix(r[0], "name_morphemes.tsv"), r[2]): (r[1], "manual")
             for r in _tsv(man / "name_morphemes.tsv")}

    # --- отчества
    patr: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for g_en, sufs in petr["middlename"]["suffixes"].items():
        for s in sufs:
            patr[(_suffix(s, "petrovich"), "suffix")] = (_G[g_en], "petrovich")
    for row in _tsv(man / "patronymic.tsv"):
        patr[(_suffix(row[0], "patronymic.tsv"), row[2])] = (row[1], "manual")

    files = {
        "names.tsv": ("name\tgender\tgroups\tsrc",
                      [f"{k}\t{g}\t{','.join(sorted(gr))}\t{src}" for k, (g, gr, src) in names.items()]),
        "name_suffixes.tsv": ("suffix\tgender\tsrc", [f"{k}\t{g}\t{src}" for k, (g, src) in name_suf.items()]),
        "surname_suffixes.tsv": ("suffix\tgender\tgroup\tsrc",
                                 [f"{k}\t{g}\t{gr}\t{src}" for k, (g, gr, src) in sur_suf.items()]),
        "surname_exact.tsv": ("surname\tgender\tgroups\tsrc",
                              [f"{k}\t{g}\t{gr}\t{src}" for k, (g, gr, src) in sur_exact.items()]),
        "syllables.tsv": ("syllable\tgender\tgroup\tsrc",
                          [f"{k}\t{g}\t{gr}\t{src}" for (k, gr), (g, src) in syl.items()]),
        "name_morphemes.tsv": ("morpheme\tgender\tposition\tsrc",
                               [f"{k}\t{g}\t{pos}\t{src}" for (k, pos), (g, src) in morph.items()]),
        "patronymic.tsv": ("marker\tgender\tkind\tsrc",
                           [f"{k}\t{g}\t{kind}\t{src}" for (k, kind), (g, src) in patr.items()]),
    }
    out = {name: head + "\n" + "\n".join(sorted(rows)) + "\n" for name, (head, rows) in files.items()}
    manifest = {
        "data_version": DATA_VERSION,
        "sources": SOURCES,
        "files": {n: {"rows": body.count("\n") - 1, "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
                  for n, body in sorted(out.items())},
    }
    manifest["names_by_src"] = REPORT.get("names_by_src", {})
    out["MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="сверить данные пакета со сборкой, ничего не писать")
    args = ap.parse_args()
    out = build()
    if args.check:
        bad = [n for n, body in out.items()
               if not (OUT / n).exists() or (OUT / n).read_bytes() != body.encode("utf-8")]
        if bad:
            print("данные rugender устарели — пересоберите:", ", ".join(bad))
            return 1
        print("данные rugender совпадают со сборкой")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, body in out.items():
        (OUT / n).write_bytes(body.encode("utf-8"))
    print("собрано:", {n: body.count("\n") - 1 for n, body in out.items() if n.endswith(".tsv")})
    print("имена по источникам:", REPORT.get("names_by_src"))
    for pair, items in REPORT.get("conflicts", {}).items():
        print(f"расхождения {pair}: {len(items)} — {', '.join(items[:12])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
