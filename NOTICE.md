# Источники данных и атрибуция

Словари rugender (`src/rugender/data/`) собраны из перечисленных ниже источников
(`data_src/`, сборщик `scripts/build_data.py`). У каждой строки словаря указан источник
(колонка `src`); сводка — в `src/rugender/data/MANIFEST.json`.

| Источник | Правообладатель | Лицензия / условия | Изменения |
|---|---|---|---|
| petrovich-rules — https://github.com/petrovich/petrovich-rules | © 2013 Petrovich Developers | MIT (`data_src/petrovich/LICENSE`) | окончания и исключения перенесены в TSV |
| «Татарско-русский словарь личных имён, отчеств и фамилий» — https://zags.tatarstan.ru/rus/tatarsko-russkiy-slovar-lichnih-imen-otchestv-i.htm | Управление ЗАГС Кабинета Министров Республики Татарстан | CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/ | извлечены имя (рус.), пол, имя (тат.) |
| «Vardų lingvistiniai duomenys» — https://data.gov.lt/datasets/2664/ | Valstybinė lietuvių kalbos komisija (VLKK) | CC BY 4.0 | однословные имена с полом, перевод в русскую запись |
| «Популярные имена» — https://stat.gov.kz/ru/instuments/name/ | Бюро национальной статистики АСПиР РК | свободное использование со ссылкой на источник (https://stat.gov.kz/ru/description/) | имена с ≥5 носителями, суммы по полу |
| «Популярные имена новорождённых» — https://data.mos.ru | Управление ЗАГС г. Москвы, Портал открытых данных Правительства Москвы | открытые данные, использование со ссылкой на портал (https://data.mos.ru/terms) | суммы по полу |
| «Personu vārdi» — https://data.gov.lv/dati/dataset/personu-vardi | Pilsonības un migrācijas lietu pārvalde (PMLP) | CC0 1.0 | однословные имена с ≥3 носителями, перевод в русскую запись |
| «Azərbaycan adları» — https://opendata.az | Министерство юстиции Азербайджанской Республики | CC0 | личные имена (без фамилий), перевод в русскую запись |
| Wikidata — https://www.wikidata.org | участники Wikidata | CC0 1.0 | частоты пола по личным именам людей СССР и 15 республик; классы имён |

Персональных данных в словарях нет: только имена и агрегированные частоты.
