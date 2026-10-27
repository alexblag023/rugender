"""rugender — офлайн-определение пола по ФИО в русской записи (народы РФ/СНГ,
китайские, вьетнамские, корейские и европейские ФИО в русской транскрипции).

    from rugender import detect
    v = detect(surname="Нгуен", name="Тхи Хоа")   # Verdict(gender='f', basis='vn_middle', …)

Без зависимостей: правила и словари — в data/ (собираются scripts/build_data.py из
data_src/; источники и лицензии — NOTICE.md).
"""
from .engine import Signal, Verdict, detect

__version__ = "0.1.0"

__all__ = ["Signal", "Verdict", "detect", "__version__"]
