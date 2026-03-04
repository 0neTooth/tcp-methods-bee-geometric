# lom-study

Исходный код и скрипты для воспроизведения методов LoM-Score и Dis-LoM-Score.

## Планируемая структура
- `cia/` — модуль анализа изменений (Java/Kotlin + Soot, ASM).
- `coverage/` — вспомогательные утилиты для подготовки матриц покрытия (Python/Java).
- `tcp/` — реализации алгоритмов приоритизации (Python).
- `experiments/` — сценарии запуска полного конвейера и обработки результатов.

## Текущее состояние
- Основной конвейер покрытия использует CLI GZoltar (список тестов, `runTestMethods` с javaagent, `faultLocalizationReport`) — см. `scripts/run_gzoltar.py`.
- Добавлен утилитарный класс `dev.mpr.gzoltar.GzoltarSerExporter` (Java 11) как задел для кастомного экспорта `gzoltar.ser`; требует доработки при необходимости.
- Добавлен `dev.mpr.cia.RocExporterMain` — CLI, вычисляющий `roc.csv` на основе байткодного diff двух версий (шаг подготовки CIA).

## Сборка и запуск ROC-экспортера
```bash
./gradlew :lom-study:jar
java -cp lom-study/build/libs/lom-study-0.1.0-SNAPSHOT.jar \
  dev.mpr.cia.RocExporterMain \
  data/raw/Jsoup/93b/build/classes/java/main \
  data/raw/Jsoup/93f/build/classes/java/main \
  data/raw/Jsoup/93/cia/roc.csv \
  data/raw/Jsoup/93/cia/modified_classes.src
```
Файл с префиксами (`modified_classes.src` или собственный) должен содержать строки с package/class в JVM-формате (`org/jsoup/`); пустые строки и `#` игнорируются.

## Автоматизация
```bash
python scripts/run_cia_roc.py --project Jsoup --bug 93
```
Скрипт соберёт классы (при необходимости), пересоберёт jar и создаст `data/raw/Jsoup/93/cia/roc.csv`. Дополнительные опции: `--skip-compile`, `--rebuild-jar`, `--include-file`, `--classpath`.

Для всего конвейера используется
```bash
python scripts/run_cia_pipeline.py --project Jsoup --bug 93
```
Он вызывает ROC, forward slicing и расчёт `impact_probabilities.csv` подряд.

```bash
python scripts/run_cia_pipeline_all.py --skip-existing
```
Пакетная обёртка, проходящая по `config/projects.csv` (доступны флаги `--resume-from`, `--skip-compile`, `--classpath`).

## Forward slicing
```bash
java -cp lom-study/build/libs/lom-study-0.1.0-SNAPSHOT.jar \
  dev.mpr.cia.SootForwardSlicer \
  data/raw/Jsoup/93f/target/classes \
  data/raw/Jsoup/93/cia/modified_classes.src \
  data/raw/Jsoup/93/cia/forward_slicing.csv
```
CLI использует Soot: строит CFG каждого метода, запускает forward slicing от параметров и сохраняет `total_units`, `sliced_units`, `probability`. Дополнительный аргумент (4-й) — файл classpath (список через `:`) при необходимости.

## Марковская модель
```bash
python scripts/run_cia_markov.py --project Jsoup --bug 93
```
Скрипт читает `roc.csv`, `forward_slicing.csv`, `callgraph.txt`, строит нормализованные переходы и сохраняет `impact_probabilities.csv`.

## LoM (каркас)
```bash
python scripts/run_lom.py --project Jsoup --bug 93 --top 10
```
Скрипт загружает матрицу покрытия и CIA-вероятности и выполняет предварительный расчёт LoM-Score (с упрощённым сопоставлением методов, требует дальнейшей доработки).

```bash
python scripts/run_lom.py --project Gson --bug 18 --mode dis-lom --top 10
```
Использует Dis-LoM (учёт схожести тестов через Jaccard).

```bash
python scripts/run_lom_all.py --skip-existing
```
Рассчитывает LoM-рейтинги для всех проектов и сохраняет CSV в `data/results/lom/<project>/<bug>/lom_scores.csv`.

```bash
python scripts/run_lom_all.py --mode dis-lom --output data/results/dis_lom
```
Пакетный расчёт Dis-LoM (результаты лежат в `data/results/dis_lom/`).

## Статус
- Структура каталога создана; реализация модулей предстоит.
