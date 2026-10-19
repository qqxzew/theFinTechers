# Stáj: промежуточный отчёт (19.10.2026, ~18:45)

Только существующие результаты и логи. Новых функций нет. Что не посчитано, помечено «ещё не рассчитано» / «нет данных». ВСЕ ДАННЫЕ СИНТЕТИЧЕСКИЕ.

## 1. Один кейс от начала до конца

**SYNTHETIC DATA** (красная команда поверх распределений ČNB). Мир: `data/redteam/seed101` (tx.parquet, clients.parquet). Скрипт: `scratchpad/interim/case_e2e.py`. Последовательность та же, что в `api/state.py::build_state`: load_world, run_banks, run_radar, apply_clusters, build_case_json.
**PLANTED scenario: same_hand_stealth** (labels.parquet прочитан только ради этого факта: label=mule, instance 10).
Выбор: среди 28 подложенных same_hand/same_hand_stealth в раскрытых кластерах взят кейс с максимальным ростом приоритета от радара.

| Поле | Значение |
|---|---|
| case_id / банк / псевдоним клиента | B1-R03035 / B1 / `c-40d0ab50` (HMAC, `copilot-secret`) |
| Профиль | физлицо, договор distant form, 74 дня клиентом, AML-риск low, PEP нет |
| Маршрут | mule_review |

**Сработавшие сигналы**

| id | детектор | score | evidence | источник |
|---|---|---|---|---|
| R-A:R03035 | R-A | 0.5 | числовых значений нет, только причина `daily_gt_share_of_projected` | FINREG rule A |
| D5:R03035 | D5 редкие выходы | 1.0 | share_rare 1.0; recurring_income_share 0.0; popular_inflow_share 0.0; out_total 65 694 CZK | own design |
| X:R03035 | радар | 0.8528 | cluster_id=e883b484c46b | Stáj radar, blinded PSI |

Смягчающих (exculpatory) сигналов нет. Фичи: 2 входа, 2 выхода, 2 цикла, drained_24h 0.90, lag_median 2.69 ч, retention_median 0.0995.

**Локальный и радарный взгляд**

| | isolated (до apply_clusters) | staj_psi (после) |
|---|---|---|
| сигналы | R-A, D5 | R-A, D5, X |
| logit / вероятность | -1.75 / 0.148 | 1.235 / 0.775 (X даёт 3.5 x 0.8528 = 2.985) |
| priority | 30 | 86 |
| triage | REVIEW (ровно на пороге 30, оба сигнала без объяснения) | REVIEW, причина «член раскрытого кластера, авто-закрытие запрещено» |

Кластер `e883b484c46b`: банки B1, B2, B3; 8 кандидатов (B1: 3, B2: 2, B3: 3); для этого клиента 2 других банка и 5 кандидатов у других; 3 совпавших ключевых токена (HMAC-идентификаторы, открытые значения не выводились); концентрация lag/retention 1.0, same_hand_global=True, score кластера 0.8528.
Id кластера в `redteam_seed101.json` (`26ca23fd2a71`, те же 8 кандидатов, тот же score) другой, потому что у eval и API разные epoch-ключи (`epoch-eval` и `epoch-demo`).
Тот же кейс отдаёт запущенный API: `GET /api/cases/B1-R03035` даёт priority 86 и сигналы R-A, D5, X, совпадающие с моим расчётом.
Ограничение: `n_cycles=2`, поэтому D6 локально не сработал. Банк B1 сам видел только слабый профиль, а группа раскрылась только через радар.

## 2. Результаты оценки

Определение рабочей точки: триаж REVIEW, route mule_review и priority >= 30. Порог 30 равен `cases.fp_max_priority`. Все метрики считает код (`eval/redteam_eval.py`), вручную ничего не набиралось.

**Актуальность файлов (mtime)**

| Файл | mtime | Статус |
|---|---|---|
| `eval/out/redteam_seed101.json` | 17:59:58 | актуален: позже последних правок node/, radar/, thresholds.yaml (17:58). Мой пересчёт совпал по числам обмена (568 / 145 408 Б / 69) и размерам кластеров 11/9/8 |
| `eval/out/redteam_seed7.json` | 17:54:03 | УСТАРЕЛ: раньше E6-E8 (17:55), thresholds (17:58) и перегенерации данных (17:59). JSON описывает 3107 клиентов / 45 мулов без same_hand_stealth, на диске сейчас 3122 клиентов / 60 мулов. Формат старый (нет operating_point, порога 30): цифры «любой приоритет», несравнимы с seed 101 |
| `eval/out/finreg_counts.json` | 17:12:40 | счётчики правил ČNB |
| `eval/report.md`, `eval/report.json` | нет | не существуют |

**Seed 101 (held-out), рабочая точка priority >= 30; 55 мулов, 3117 счетов, 219 140 tx**

| Режим | tp | fp | fn | precision | recall | f1 | Раскрыто записей / байт |
|---|---|---|---|---|---|---|---|
| isolated | 48 | 7 | 7 | 0.8727 | 0.8727 | 0.8727 | 0 / 0 |
| staj_psi | 48 | 7 | 7 | 0.8727 | 0.8727 | 0.8727 | 0 сырых; 568 blinded-элементов, 145 408 Б, 69 строк координатору |
| naive_raw_sharing | 45 | 6 | 10 | 0.8824 | 0.8182 | 0.8491 | 219 140 / 19 410 461 |

Без порога (любой приоритет): isolated и staj_psi 55/25/0 (P 0.6875, R 1.0, F1 0.8148); naive 55/21/0 (P 0.7237, F1 0.8397).
По банкам (isolated, порог 30): B1 18/2/2 F1 0.900; B2 15/2/3 F1 0.857; B3 15/3/2 F1 0.857. Лучший одиночный банк 0.900, средний 0.8714.

**По схемам и персонам, seed 101** (staj_psi = isolated при пороге 30)

| Группа | n | помечено как mule-кейс |
|---|---|---|
| mule/same_hand | 20 | 20 |
| mule/same_hand_stealth | 15 | 8 (53.3 %) |
| mule/day_zero | 8 | 8 |
| mule/invoice_mule | 6 | 6 |
| mule/fixed_skim | 6 | 6 |
| victim | 8 | 0 mule; 7 направлены в victim_protection (87.5 %) |
| honest: group_collection 6, migrant_remit 10, second_hand_seller 10, freelancer 10, students_rent 6, middleman_cohost 6, fundraiser 6 | 54 | 0 из 54 |
| background (ČNB) | 3000 | 7 (0.23 %) |

Без порога 30 (любой приоритет) честные персоны помечались бы: fundraiser 6/6, middleman_cohost 6/6, group_collection 3/6; фон 10/3000. Нулевой FP у честных персон держится на пороге 30, и эту оговорку надо озвучивать.
Отдельной оценки «mom» (E1) нет. Ближайший аналог migrant_remit даёт 0/10.

**Абляции, seed 101 (порог 30)**

| Вариант | tp | fp | fn | P | R | F1 |
|---|---|---|---|---|---|---|
| полная система (staj_psi) | 48 | 7 | 7 | 0.873 | 0.873 | 0.873 |
| без слоя невиновности | 48 | 22 | 7 | 0.686 | 0.873 | 0.768 |
| без радара | 48 | 7 | 7 | 0.873 | 0.873 | 0.873 |
| без D6/D7 | 35 | 7 | 20 | 0.833 | 0.636 | 0.722 |

**«С радаром и без радара»**
- Seed 101: идентично (48/7/7 на пороге 30 и 55/25/0 без порога). Ablation `without_radar` в коде просто копирует isolated (`abl["without_radar"] = isolated`), то есть это не независимый прогон.
- Seed 7 (устаревший JSON): тоже идентично (45/41/0).
- Все 28 мулов в кластерах и так были REVIEW с priority >= 30 локально. Радар поднял им priority на +16...+56 пунктов (диапазон по моему пересчёту) и запретил авто-закрытие, но состав множества на пороге 30 не изменил.
- 7 пропущенных stealth-мулов (priority 10-19, только R-A, у одного ещё D3) в кластеры не попали. Вероятно, их вероятность (R-A: logit -3.75, около 0.023) ниже `token_export.min_prob`=0.05 и токены не экспортируются. Это вывод из конфига, отдельно не проверен.
- Неофициальная диагностика лидера: `scratchpad/audit_radar/out101_minprob.txt`, не в eval/out, мной не воспроизведена. При порогах 40-70 на seed 101 радар помогает: порог 40, isolated R 0.818 при FP 0, psi R 0.873 при FP 0; порог 70, isolated 30 tp, psi 43 tp; AP 0.971 и 0.976. Этот же файл показывает, что seed 101 использовался в sweep по min_prob и порогам.

**Радарные кластеры, seed 101** (раскрыто 3, `refused` пусто)

| cluster_id (eval) | банки | кандидатов | score | lag/ret conc. |
|---|---|---|---|---|
| 01035b239218 | B1,B2,B3 | 11 | 0.9278 | 1.0 |
| 21d1c20074d0 | B1,B2,B3 | 9 | 0.8681 | 1.0 |
| 26ca23fd2a71 | B1,B2,B3 | 8 | 0.8528 | 1.0 |

Метки кандидатов в раскрытых кластерах: mule 28, honest 0, background 0. Seed 7 (устар.): 2 кластера (11 и 14 кандидатов), mule 25.

**Худшие FP (seed 101, 7 штук, все background):** R02619 (приоритет 37: R-A, R-B, D3; E2 объясняет R-A и D3, R-B без объяснения), R02590 (36), R00726 (32: R-A, R-C, D3), R01910 (31), R00843 (31), R00709 (30), R01145 (30). У пяти из них (R02590, R01910, R00843, R00709, R01145) все сигналы объяснены E2/E3/E4, но priority >= 30 запрещает авто-закрытие; у R02619 и R00726 остаётся необъяснённый R-B или R-C.
**FN (7, все same_hand_stealth):** R03029 (10), R03030 (17), R03031 (12), R03033 (19, R-A+D3), R03039 (14), R03040 (12), R03041 (18). Сигнал только R-A, смягчающих нет, priority < 30.

**Seed 7 (устар., «любой приоритет»):** isolated = staj_psi: 45/41/0, P 0.523, R 1.0, F1 0.687; naive 45/35/0 (F1 0.72); без слоя невиновности 45/2553/0 (F1 0.034); без радара и без D6/D7 = 45/41/0. Обмен psi 428 элементов / 109 568 Б. Честные персоны там помечены: students_rent 6/6, middleman 6/6, group_collection 6/6, fundraiser 6/6, freelancer 5/10; фон 12 и ещё 44 в victim_protection. Это состояние до E6-E8 и нового порога, поэтому для презентации непригодно. Нужно перегенерировать (ещё не рассчитано на текущем коде).

**Правила ČNB (`finreg_counts.json`, 397 853 tx, 5 493 клиента)**

| Правило | Алертов |
|---|---|
| A, monthly/quarterly (по умолчанию) | 4 669 |
| A, monthly/monthly | 3 313 |
| A, quarterly/quarterly | 5 012 |
| A, yearly/* | 5 473-5 489 |
| B | 4 (все PEP) |
| C (threshold_crossing) | 16 |
| C (first_inflow) | 18 |

Правило A срабатывает на 60 % (3 313) и до 99.9 % клиентов при любой трактовке единиц.
Не найдено в `eval/out` (нет файлов): оценка триажа ČNB по правилу C (FP/REVIEW) и `cnb_eval.json`; IBM AMLworld (сырые данные в `data/raw/ibm`, оценки нет); отдельный FP-rate «mom»-персоны. Всё: **ещё не рассчитано**.

## 3. Amazon Bedrock

`config/models.yaml`, регион eu-central-1, профиль `hackathon`:

| Роль | Model ID |
|---|---|
| agent_primary | `global.moonshotai.kimi-k3` (не Anthropic) |
| fallback | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| bulk | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |

Лимиты: 12 шагов, 60 000 токенов, 0.50 USD, 180 с. Цены в конфиге заглушки (placeholders), поэтому стоимость ниже ориентировочная. `read_timeout` в `copilot/model_registry.py` сейчас 300 с, retries max_attempts=2.

**Live-тест** (`be7zt1ryc.output`, кейс `R03001`, 5 сигналов, priority 79)
- `verify`: все три роли `ok` (tool-use smoke test), 48.8 с суммарно.
- Затем `explain_case` упал с `BudgetExceeded: timeout 120s exceeded` (`explain.py:68`, `budget.check_time()`). Объяснение EN/CS и раздел V OPO этим прогоном НЕ получены. Бюджет создаётся прямо перед `explain_case`, так что до исключения шла минимум одна успешная попытка и повторы (мой вывод по коду). Лимит 120 с задан в самом `live_copilot.py` (`Budget(6, 60000, 1.0, 120)`) и ниже таймаута клиента 300 с.
- Первый прогон (по сообщению лидера) упал с `ReadTimeoutError` на 60 с, исправлено (300 с подтверждено в коде).
- Новее есть `tasks/bm4i61vqu.output` (18:42). Моим доступом он не охвачен и мной не читался.

**Аудит завершённых вызовов** (`eval/out/audit_live_*.jsonl`; файла `audit_live_copilot.jsonl` нет, значит имя вывода в скрипте разошлось с файлами)

| Файл | модель | вызовов | токенов | оценка стоимости | интервалы между успешными вызовами |
|---|---|---|---|---|---|
| audit_live_fallback.jsonl | Sonnet 4.5 (eu) | 5 | 25 095 | 0.182 USD | 14.5, 27.0, 12.6, 12.6 с (верхняя оценка латентности) |
| audit_live_agent_primary.jsonl | Kimi K3 (global) | 2 | 10 121 | 0.022 USD | 50.0 с между 1-м и 2-м |

В аудите только хеши входа и выхода, текста ответов нет. Прямой латентности запроса нет в логах. Отдельные цитаты (EN-объяснение, одно предложение на чешском, раздел V, нарушения QA): **нет данных**, в доступных файлах текстов нет.
Следующий диагностический шаг: перезапустить `live_copilot.py` с лимитом `Budget` не менее 300 с и с записью `print` в файл (`> out.txt`), чтобы сохранились текст ответа и `violations`. Заодно выяснить, чем отличаются 5 вызовов Sonnet (у них разные `input_hash`: это либо retry с обратной связью QA, либо разные кейсы; по аудиту не определить).
**Воркеры** (`orchestrator/runs/*.jsonl`, модель по умолчанию Kimi K3): 51 запуск, 43 accepted, 7 blocked, 1 step_limit (`t003_fx_config`); сумма токенов по записям 1 806 399. Blocked в основном из-за песочницы (в системном Python нет numpy, `.venv` запрещён): r01-r04, t030, x02, g02. Код этих модулей в репозитории есть, тесты проходят.

## 4. Как посмотреть результат

Корень: `C:\Users\fandr\Desktop\TheFinCathers\staj`. Python: `.venv/Scripts/python`.
- Генерация мира: `cd C:/Users/fandr/Desktop/TheFinCathers/staj && PYTHONPATH=. .venv/Scripts/python -m redteam.generate --seed 101 --out data/redteam/seed101`
- Оценка (шаблон `scratchpad/run_eval.py`): `PYTHONPATH=. .venv/Scripts/python -c "from eval.redteam_eval import evaluate; import json; r=evaluate('data/redteam/seed101', audit_path='eval/out/audit_seed101.jsonl'); print(r['modes']['staj_psi']['overall'])"` (около минуты; сам скрипт пишет `eval/out/redteam_seed<N>.json`)
- Кейс end to end: `PYTHONIOENCODING=utf-8 PYTHONPATH=. .venv/Scripts/python <scratchpad>/interim/case_e2e.py B1-R03035`
- Тесты: `PYTHONPATH=. .venv/Scripts/python -m pytest tests -q` дали **97 passed, 0 failed, 15 с**. Тестов на `api/` и `ui/` нет; в `test_copilot_core.py` 6 тестов на фейковом клиенте без живого Bedrock.
- API: `python -m api.server` (хост 127.0.0.1, порт 8000, мир из `STAJ_WORLD`). `python -c "import api.server"` проходит. **Сервер уже запущен** (порт 8000, PID 27928, не мной). Мои GET-запросы ответили: `/api/meta`, `/api/queue` (alerts_before_triage 2692, cases 2674, review 87, fp_auto_closed 2587, victim_protection 7), `/api/cases/B1-R03035`, `/api/radar` (200), `/api/metrics`, `/api/honesty`, `/api/audit/verify` (`ok: true`, длина цепочки 2683). POST-эндпоинты не вызывались. Swagger: http://localhost:8000/docs (грузит скрипты с CDN). Корень `/` отвечает 404, UI им не отдаётся.
- UI (`ui/`, делает другой агент, не трогал): `package.json`, vite/tailwind/tsconfig, `index.html`, `src/types.ts`, `src/components/ui.tsx`, `scripts/gen-mocks.mjs`, `public/mock/*` (JSON-моки, 2 OPO .md, CSV); `src/screens/` пуст. `node_modules` есть (131 пакет), `dist` нет. Vite на 5173 и 5174 не отвечает (curl): UI не запущен и экранов ещё нет.

**Файлы (абсолютные пути)**
- `C:\Users\fandr\Desktop\TheFinCathers\staj\docs\DECISIONS.md` (D-001...D-009, последняя правка 17:21, решений по red-team/оценке/D6 в нём нет), `docs\honesty.json` (новый, 18:42), `docs\MASTER_PROMPT.md`
- `...\staj\eval\out\redteam_seed101.json`, `redteam_seed7.json` (устар.), `finreg_counts.json`, `audit_seed101.jsonl`, `audit_demo.jsonl`, `audit_live_fallback.jsonl`, `audit_live_agent_primary.jsonl`
- `...\staj\config\`: `thresholds.yaml`, `models.yaml`, `units.yaml`, `fx.yaml`, `high_risk_jurisdictions.yaml`, `escalation_matrix.yaml` (заглушка), `bank_settings.yaml` (заглушка)
- PSI: `...\staj\radar\psi\dh_psi.py`; радар: `radar\sessions.py`, `radar\clustering.py`, `radar\guards.py`

## 5. Итоговые списки

**(a) Работает и проверено тестами/оценкой**
- 97 тестов проходят (ČNB-ингест, правила A/B/C, фичи, детекторы, слой невиновности, кейсы, PSI-свойства, радар e2e, схемы red-team, цепочка аудита, ядро copilot на фейках).
- Конвейер банка, PSI-радар и кластеризация на seed 101: 48/7/7, 28 из 28 кандидатов в кластерах настоящие мулы, сырых данных наружу 0 (568 blinded-элементов, 145 КБ против 19.4 МБ у naive).
- Слой невиновности: без него FP растёт с 7 до 22 (seed 101).
- D6/D7: без них recall падает с 0.873 до 0.636.
- Bedrock: все три модели отвечают на tool-use (verify ok, 48.8 с). Есть 7 завершённых вызовов в аудите (Sonnet 4.5: 5, Kimi K3: 2).
- API: импортируется, GET-эндпоинты отвечают, цепочка аудита `ok`.

**(b) Написано, но НЕ проверено**
- Текст объяснения EN/CS, раздел V OPO и QA-валидатор на живом ответе модели (тестировались только на фейках). Текстов нет.
- API: POST-эндпоинты (decision, explain, PUT section-v) и тестов на `api/` нет.
- UI: экранов нет, только моки и типы.
- Матрица эскалации и реквизиты банка: заглушки. FX-курсы: заглушка (`fx_placeholder: true`).
- Список ЕС по высокорисковым юрисдикциям в D-005 помечен «to be verified».
- `redteam_seed7.json` устарел, на текущем коде не пересчитан.
- Оценка по IBM AMLworld и триаж правила C на ČNB: ещё не рассчитано.

**(c) Что блокирует первый сквозной демо-прогон**
1. Нет ни одного завершённого живого ответа copilot (объяснение + раздел V): исправить `Budget` (120 с) и сохранить вывод.
2. UI: экраны не написаны, `dist` нет.
3. Нужен единый прогон: перегенерировать seed 7 на текущем коде, чтобы обе метрики были сопоставимы.
4. Решить, что показывать как рабочую точку: порог 30 даёт 0 FP на честных персонах, но 7 пропущенных stealth-мулов и 7 FP на фоне.

**Честные оговорки (говорить явно)**
- Данные ČNB не содержат сетей мулов (D-009: relay-совпадения равны перетасованному baseline). Все схемы мулов подложены red-team, это синтетика, а не обнаружение реальных сетей.
- `volume_is_czk: true` подтверждено прямым тестом (медиана `volume` около 3 000 для всех валют, D-006b). Обратное прочтение даёт срабатывание правила A почти у всех.
- Правило A срабатывает у 60-99.9 % клиентов при любой трактовке единиц (D-008). Практическую очередь делает слой триажа, а не само правило.
- Подбор D6 и band делался на seed 7, held-out это seed 101. Однако на seed 101 уже прогонялись sweep по min_prob и порогам (скрипты и вывод в scratchpad), поэтому его «held-out» статус ослаблен.
- Слой невиновности E6-E8 и порог 30 появились после того, как seed 7 показал FP на тех же честных персонах (mtime seed7 JSON 17:54, E6-E8 17:55). Нулевой FP на этих персонах не является независимым доказательством.
- Генератор персон и детекторы написаны одной командой.
- Радар на seed 101 на рабочей точке метрик не меняет, меняет приоритет и запрет авто-закрытия. Выигрыш по метрикам виден только в неофициальных sweep'ах.
- naive_raw_sharing (слияние всех данных в один узел) хуже isolated по recall (0.818 против 0.873). Причина не исследована, поэтому «naive как верхняя граница» тут не выполняется.




