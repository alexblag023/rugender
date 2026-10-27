"""Перевод имён из латиницы балтийских языков в русскую запись (для сборки словарей
rugender, не для рантайма). Практическая транскрипция по общим правилам; цель —
совпасть с тем, как имя пишут в российских документах, поэтому для мужских имён
даём и вариант без окончания «-с» (Sergejs → «Сергейс» и «Сергей»).

    lv_to_ru("Jānis") → ["янис"];  lv_to_ru("Aleksandrs") → ["александрс", "александр"]
    lt_to_ru("Jonas") → ["йонас"]; lt_to_ru("Liudas") → ["людас"]
"""
from __future__ import annotations

import re
from typing import List

_VOWELS = "aeiouyāēīūąęėįųū"

# Смягчённые согласные + гласная → мягкая пара: ļa → ля, ņe → не.
_SOFT = {"a": "я", "ā": "я", "e": "е", "ē": "е", "u": "ю", "ū": "ю", "o": "ё", "i": "и", "ī": "и"}

_LV = {"a": "а", "ā": "а", "b": "б", "c": "ц", "č": "ч", "d": "д", "e": "е", "ē": "е", "f": "ф",
       "g": "г", "ģ": "г", "h": "х", "i": "и", "ī": "и", "k": "к", "ķ": "к", "l": "л", "ļ": "ль",
       "m": "м", "n": "н", "ņ": "нь", "o": "о", "p": "п", "r": "р", "s": "с", "š": "ш", "t": "т",
       "u": "у", "ū": "у", "v": "в", "z": "з", "ž": "ж", "y": "и", "x": "кс", "w": "в", "q": "к"}

_LT = {"a": "а", "ą": "а", "b": "б", "c": "ц", "č": "ч", "d": "д", "e": "е", "ę": "е", "ė": "е",
       "f": "ф", "g": "г", "h": "х", "i": "и", "į": "и", "y": "и", "k": "к", "l": "л", "m": "м",
       "n": "н", "o": "о", "p": "п", "r": "р", "s": "с", "š": "ш", "t": "т", "u": "у", "ų": "у",
       "ū": "у", "v": "в", "z": "з", "ž": "ж", "x": "кс", "w": "в", "q": "к"}


def _convert(word: str, table: dict, soft: str) -> str:
    w = word.strip().lower()
    out: List[str] = []
    i = 0
    while i < len(w):
        c, nxt = w[i], (w[i + 1] if i + 1 < len(w) else "")
        prev = w[i - 1] if i else ""
        if c == "d" and nxt and nxt in "žz":              # dž → дж, dz → дз
            out.append("дж" if nxt == "ž" else "дз")
            i += 2
            continue
        if c == "i" and nxt == "j" and prev and prev in _VOWELS:   # Maija → Майя
            after = w[i + 2] if i + 2 < len(w) else ""
            out.append("й" + _SOFT[after] if after in _SOFT else "й")
            i += 3 if after in _SOFT else 2
            continue
        if c == "j" and nxt in _SOFT:
            # ja → я в начале (Jana → Яна), после согласной — ья (Tatjana → Татьяна),
            # после гласной — йя (Raja → Райя); «jo» — йо (Jonas → Йонас).
            soft_v = "йо" if nxt == "o" else _SOFT[nxt]
            if not prev:
                out.append(soft_v)
            elif prev in _VOWELS or prev == "i":
                out.append(soft_v if soft_v == "йо" else "й" + soft_v)
            else:
                out.append("ь" + soft_v if soft_v != "йо" else "ьо")
            i += 2
            continue
        if c == "j":
            out.append("й")
            i += 1
            continue
        if c in soft and nxt in _SOFT:                     # ļa → ля, ņu → ню
            out.append(table[c][0] + _SOFT[nxt])
            i += 2
            continue
        if c == "i" and nxt and nxt in "aāouū" and prev and prev not in _VOWELS:   # лит. Liudas → Людас
            out.append(_SOFT[nxt])
            i += 2
            continue
        if c in "eē" and (not prev or prev in _VOWELS) and not (prev == "i"):
            out.append("э")                                # начало слова/после гласной: Edgars → Эдгарс
            i += 1
            continue
        out.append(table.get(c, ""))
        i += 1
    return "".join(out)


def _variants(ru: str, male: bool) -> List[str]:
    out = [ru]
    # Мужское «-с» после согласной или «й» — грамматическое окончание; в русской записи
    # заимствованных имён его нет (Aleksandrs → Александр, Sergejs → Сергей).
    if male and len(ru) > 4 and ru[-1] == "с" and ru[-2] not in "аеиоуыэюяё":
        out.append(ru[:-1])
    return out


# Азербайджанская латиница → русская запись по сложившейся традиции документов:
# h, q → г (Həsən → Гасан, Qəmbər → Гамбар), c → дж (Cavid → Джавид), ə → а (Əli → Али),
# ü → ю, ö → ё, ı → ы; «l» перед согласной — «ль» (Elnur → Эльнур, Gülnar → Гюльнар).
_AZ = {"a": "а", "b": "б", "c": "дж", "ç": "ч", "d": "д", "e": "е", "ə": "а", "f": "ф", "g": "г",
       "ğ": "г", "h": "г", "x": "х", "ı": "ы", "i": "и", "j": "ж", "k": "к", "q": "г", "l": "л",
       "m": "м", "n": "н", "o": "о", "ö": "ё", "p": "п", "r": "р", "s": "с", "ş": "ш", "t": "т",
       "u": "у", "ü": "ю", "v": "в", "y": "й", "z": "з", "w": "в"}
_AZ_VOWELS = "aeəıioöuü"
_AZ_YV = {"a": "я", "ə": "я", "u": "ю", "ü": "ю", "o": "ё", "e": "е", "ı": "ы", "i": "и"}


def az_to_ru(word: str) -> List[str]:
    """Варианты русской записи: традиция непоследовательна (Гюльнар, но Гусейн; Гасан,
    но Шахла) — в словарь идут все, пол у них один."""
    out = []
    for u in ("ю", "у"):
        for h in ("г", "х"):
            v = _az_one(word, u, h)
            if v not in out:
                out.append(v)
    return out


def _az_one(word: str, u_sound: str, h_sound: str) -> str:
    w = word.strip().lower().replace("i̇", "i")
    out: List[str] = []
    i = 0
    while i < len(w):
        c, nxt = w[i], (w[i + 1] if i + 1 < len(w) else "")
        prev = w[i - 1] if i else ""
        if c == "y" and nxt and nxt in _AZ_YV:             # ya → я, yu → ю (Yusif → Юсиф)
            out.append(("й" if prev and prev in _AZ_VOWELS and nxt not in "ei" else "") + _AZ_YV[nxt])
            i += 2
            continue
        if c in "eə" and not prev:                         # Elnur → Эльнур, Əli → Али
            out.append("э" if c == "e" else "а")
            i += 1
            continue
        if c in "üö" and prev in ("", ) :                  # Ülviyyə → Ульвия, Ömər → Омар
            out.append("у" if c == "ü" else "о")
            i += 1
            continue
        if c == "l" and nxt and nxt not in _AZ_VOWELS:      # Elnur → Эльнур
            out.append("ль")
            i += 1
            continue
        if c == nxt and c not in _AZ_VOWELS and c == "y":   # -iyyə → -ия
            i += 1
            continue
        if c == "l" and not nxt and prev in "eiü":         # Aysel → Айсель, Günel → Гюнель
            out.append("ль")
            i += 1
            continue
        if c == "ü":
            out.append(u_sound)
            i += 1
            continue
        if c == "h":
            out.append(h_sound)
            i += 1
            continue
        out.append(_AZ.get(c, ""))
        i += 1
    r = "".join(out)
    # -iyyə/-iyə → -ия (Ülviyyə → Ульвия), «йй» после «и» не пишется
    return r.replace("ийя", "ия").replace("ийа", "ия")


def lv_to_ru(word: str, male: bool = False) -> List[str]:
    return _variants(_convert(word, _LV, soft="ļņķģ"), male)


def lt_to_ru(word: str, male: bool = False) -> List[str]:
    return [_convert(word, _LT, soft="")]


if __name__ == "__main__":
    for w, m in [("Jānis", 1), ("Aleksandrs", 1), ("Sergejs", 1), ("Jeļena", 0), ("Ieva", 0), ("Maija", 0),
                 ("Edgars", 1), ("Kārlis", 1), ("Bērziņš", 1), ("Džeina", 0), ("Ņina", 0), ("Tatjana", 0)]:
        print(w, lv_to_ru(w, bool(m)))
    for w in ["Həsən", "Hüseyn", "Elnur", "Gülnar", "Cavid", "Qəmbər", "Ülviyyə", "Ömər", "Yusif", "Aysel",
              "Günel", "Nərmin", "Səbinə", "Vüqar", "Xədicə", "Şəhla", "Leyla", "Zümrüd"]:
        print(w, az_to_ru(w))
    for w in ["Jonas", "Liudas", "Gintarė", "Aušra", "Juozas", "Vytautas", "Eglė", "Jurgis", "Rūta", "Kęstutis"]:
        print(w, lt_to_ru(w))
