"""Нормализация частей ФИО для словарей и правил rugender.

Словари хранятся в нижнем регистре, «ё» → «е», NFC. Вход бывает грязным: ЗАГЛАВНЫЕ,
«ё», латинские двойники кириллических букв внутри слова («Ивaнов» с латинской «a»),
латиница целиком («Ivanova»), инициалы («И.»), заглушки («-», «нет»), двойные
части через дефис или пробел.
"""
from __future__ import annotations

import re
import unicodedata
from typing import List

# Латинские буквы, неотличимые на глаз от кириллических, — в кириллическом слове.
_HOMOGLYPHS = str.maketrans("aeopcxykmthbABEKMHOPCTXY", "аеорсхукмтнвАВЕКМНОРСТХУ")
_CYR = re.compile(r"[а-яё]", re.I)
# Буквы казахской, таджикской, башкирской, татарской, чувашской кириллицы → ближайшие
# русские: словари в русской записи («Серікқызы» → «сериккызы», признак «кызы» на месте).
_NATIONAL = str.maketrans("қғұүөәіңһҳӯӣҷҙҫӊӑӗӳҡ", "кгууоаинххуичзснаеук")
_LAT = re.compile(r"^[a-z']+$")
_JUNK = {"-", "--", "нет", "н/д", "нд", "отсутствует", "null", "none", "x", "х"}

# Латиница → кириллица (паспортная транслитерация в обратную сторону, грубо:
# нужна для окончаний и словаря, а не для печати).
_LAT_MULTI = (("shch", "щ"), ("sch", "щ"), ("yo", "е"), ("zh", "ж"), ("kh", "х"), ("ts", "ц"),
              ("ch", "ч"), ("sh", "ш"), ("yu", "ю"), ("ya", "я"), ("ye", "е"), ("iy", "ий"),
              ("yy", "ый"), ("ay", "ай"), ("ey", "ей"), ("oy", "ой"), ("uy", "уй"))
_LAT_ONE = str.maketrans({"a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "e": "е", "z": "з",
                          "i": "и", "y": "ы", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
                          "p": "п", "r": "р", "s": "с", "t": "т", "u": "у", "f": "ф", "h": "х",
                          "c": "к", "w": "в", "x": "кс", "j": "дж", "q": "к", "'": ""})


def latin_to_cyr(word: str) -> str:
    w = word[:-2] + "ay" if word.endswith("ai") else word      # Mai → «май», Thai → «тхай»
    for a, b in _LAT_MULTI:
        w = w.replace(a, b)
    return w.translate(_LAT_ONE)


def norm_word(word: str) -> str:
    """Одно слово → ключ словаря ('' — пусто, инициал или заглушка)."""
    w = unicodedata.normalize("NFC", str(word or "")).strip().strip(".,;:()\"'«»")
    if not w or w.lower() in _JUNK:
        return ""
    if _CYR.search(w):
        w = w.translate(_HOMOGLYPHS)
    w = w.lower().replace("ё", "е").translate(_NATIONAL)
    if _LAT.match(w):
        w = latin_to_cyr(w)
    if len(w) <= 1 or not re.search(r"[а-я]", w):
        return ""                       # инициал или не слово
    return w


def tokens(value) -> List[str]:
    """Поле ФИО → значимые слова (по пробелам и дефисам; инициалы отброшены)."""
    raw = str(value or "")
    # Инициалы, слипшиеся с точками («И.И.»), — тоже по отдельности.
    parts = re.split(r"[\s\-‐–—_/]+|\.(?=\S)", raw)
    return [w for w in (norm_word(p) for p in parts) if w]
