"""rugender: правила, нормализация, воспроизводимость данных и качество на корпусе."""
import importlib.util
from pathlib import Path

import pytest

from rugender import detect
from rugender.normalize import norm_word, tokens

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("raw, key", [
    ("ИВАНОВА", "иванова"), ("Семёнова", "семенова"), ("Ивaнов", "иванов"),   # латинская «a»
    ("Ivanova", "иванова"), ("И.", ""), ("-", ""), ("Серікқызы", "сериккызы"),
])
def test_norm_word(raw, key):
    assert norm_word(raw) == key


def test_tokens_дефисы_и_инициалы():
    assert tokens("Гасан-оглы") == ["гасан", "оглы"]
    assert tokens("И.И.") == []


@pytest.mark.parametrize("fio, gender, basis", [
    (("Иванов", "Иван", "Иванович"), "m", "patronymic"),
    (("Сидоров", "Мария", "Ивановна"), "f", "patronymic"),         # отчество важнее имени
    (("Мамедов", "Эльчин", "Гасан оглы"), "m", "particle"),
    ((None, None, "Нурланкызы"), "f", "particle"),                   # частица слитно
    (("Нгуен", "Тхи Хоа", None), "f", "vn_middle"),
    (("Нгуен", "Хунг", "Ван"), "m", "vn_middle"),                    # среднее имя в поле отчества
    (("Ван", "Сяомэй", None), "f", "name"),                          # «Ван» — китайская фамилия
    (("Чжан", "Цзинмэй", None), "f", "syllables"),                    # имени нет в словаре — по слогам
    (("Шэнь", "Гуйин", None), "f", "syllables"),                      # «-н» у китайского имени — не мужской
    (("Чой", "Джи Ын", None), "f", "syllables"),                      # корейское имя слогами
    (("Ле", "Ань", "Нгок"), "f", "name"),                             # вьетн. имя в поле отчества
    (("Tran Thi Mai", None, None), "f", "vn_middle"),
    (("Исмайылзаде", "Гюльтарима", None), "f", "morpheme"),
    ((None, "Тлеумырзабай", None), "m", "morpheme"),
    (("Казлаускене", None, None), "f", "surname_suffix"),
    (("Петросян", "Ануш", None), "f", "name"),
    (("Ли", "Велимира", None), "f", "name_suffix"),                    # кореянка СНГ: имя русское, вне словаря
    (("Пак", "Саша", None), "", "none"),                              # честно не определено
    (("Черных", None, None), "", "none"),
])
def test_detect(fio, gender, basis):
    v = detect(*fio)
    assert (v.gender, v.basis) == (gender, basis), v.evidence


def test_противоречие_имени_и_фамилии_видно():
    v = detect("Иванова", "Никита")
    assert (v.gender, v.confidence) == ("m", "low")
    assert {s.rule for s in v.evidence} == {"name", "surname_suffix"}


def test_фамилия_на_ич_не_отчество():
    assert detect("Бабич", "Светлана").gender == "f"
    assert detect("Петрович", None, None).gender == ""


def test_данные_пакета_совпадают_со_сборкой():
    # Данные src/rugender/data руками не правят: только data_src + сборщик.
    build = _load("build_data")
    out = build.build()
    for name, body in out.items():
        assert (build.OUT / name).read_bytes() == body.encode("utf-8"), f"{name}: пересоберите данные"
    assert build.build() == out                                          # детерминизм


def test_качество_на_корпусе():
    ev = _load("evaluate")
    stat = ev.evaluate(ev.load(), ev.rugender_fn)
    total = stat["ВСЕГО"]
    assert total["n"] >= 380
    # Пороги — нижняя граница достигнутого (scripts/evaluate.py): регрессия ловится тут.
    assert total["acc"] >= 0.99 and total["undet_rate"] <= 0.02, total
    for group, s in stat.items():
        assert s["acc"] >= 0.95, (group, s["errors"])


def test_качество_на_слепом_корпусе():
    # corpus_blind.tsv составил независимый автор, не видевший словарей; по его ошибкам
    # улучшались правила (не словари) — это рабочий набор. Пороги — нижняя граница
    # достигнутого: точность на решённых, итог с умолчанием «м», доля женщин с «м».
    ev = _load("evaluate")
    stat = ev.evaluate(ev.load(ROOT / "tests" / "corpus_blind.tsv"), ev.rugender_fn)
    total = stat["ВСЕГО"]
    assert total["n"] >= 460
    assert total["acc"] >= 0.99 and total["final_acc"] >= 0.97 and total["f2m_rate"] <= 0.06, total


def test_скорость():
    # Приём реестра — тысячи карточек: 10 000 определений должны укладываться в секунды.
    import time
    detect("Иванова", "Мария", None)                      # загрузка данных — один раз
    t = time.perf_counter()
    for _ in range(2000):
        for fio in (("Иванова", "Мария", "Петровна"), ("Нгуен", "Тхи Хоа", None), ("Ван", "Сяомин", None),
                    ("Казлаускене", "Бирута", None), ("Пак", "Саша", None)):
            detect(*fio)
    assert time.perf_counter() - t < 3.0
