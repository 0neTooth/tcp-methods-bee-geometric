# tcp

Репозиторий с воспроизводимым экспериментальным pipeline для **Test Case Prioritization (TCP)** на данных **Defects4J**.

> Данный репозиторий является расширением исходного TCP-pipeline, разработанного М. А. Руденко под руководством В. А. Пархоменко.
> Оригинальная инфраструктура pipeline сохранена, а изменения, добавленные в рамках данной работы Е. В. Дубининым, описаны ниже.

## Добавлено в данной работе


В рамках данной работы репозиторий был расширен двумя алгоритмами приоритизации тестов:

- Bee Colony Prioritization
- Geometric Combined Prioritization

Новые методы реализованы на Java в пакете:

`lom-study/src/main/java/dev/mpr/tcp/`

Добавленные файлы:

- `BeeColonyMain.java`
- `BeeColonyPrioritizer.java`
- `BeeSolution.java`
- `CoverageFitness.java`
- `GeometricCombinedMain.java`
- `GeometricCombinedPrioritizer.java`
- `GeometricDataLoader.java`
- `OrderWriter.java`

Также был изменён скрипт:

- `scripts/run_tcp_benchmarks.py`

Новые методы интегрированы в общий benchmark и сравниваются с существующими методами по метрике APFD.

Ниже приведено описание исходного pipeline, на основе которого выполнено расширение.

Проект объединяет:
- сбор покрытия тестов (GZoltar),
- мутационный анализ (Major через Defects4J),
- change impact analysis (ROC + forward slicing + Markov),
- алгоритмы приоритизации тестов (LoM, Dis-LoM, CovClustering),
- сравнение с TCP-baseline и расчёт APFD.

## Что реализовано

### Основные алгоритмы приоритизации

| Метод | Идея | Входы | Выход |
|---|---|---|---|
| `LoM` | Оценка теста по среднему top-k impact-вероятностей покрываемых методов | `coverage/matrix.csv`, `cia/impact_probabilities.csv` | `data/results/lom/<project>/<bug>/lom_scores.csv` |
| `Dis-LoM` | LoM + штраф за схожесть с уже выбранными тестами (Jaccard) | `coverage/matrix.csv`, `cia/impact_probabilities.csv` | `data/results/dis_lom/<project>/<bug>/dis_lom_scores.csv` |
| `CovClustering` | Кластеризация тестов по coverage-векторам + additional внутри кластеров + round-robin между кластерами | `coverage/matrix.csv` | `data/results/cov_clustering/<project>/<bug>/cov_clustering_scores.csv` |

### TCP-baselines (для сравнения)

Скрипт `scripts/run_tcp_benchmarks.py` считает и сохраняет порядки:
- `total`
- `additional`
- `random_seed1..5`

Порядки пишутся в `data/results/tcp/<project>/<bug>/*_order.csv`, APFD — в `docs/lom_reports/tcp_apfd_results.csv`.

### Метрики
`APFD = 1 - (sum(TF_i)/(n*m)) + 1/(2n)`
где `n` — число тестов, `m` — число убивающих тестов (killed mutants), `TF_i` — позиция первого теста, обнаружившего `i`-й мутант.

## CIA pipeline

Этапы CIA запускаются для каждой версии

1. `ROC` (`scripts/run_cia_roc.py`)
- Сравнение байткода buggy/fixed и экспорт `roc.csv`.

2. `Forward slicing` (`dev.mpr.cia.SootForwardSlicer`, обёртка `scripts/run_cia_pipeline.py`)
- Экспорт `forward_slicing.csv` с вероятностями по методам.

3. `Markov` (`scripts/run_cia_markov.py`)
- Объединяет `roc.csv`, `forward_slicing.csv`, `callgraph.txt` и строит `impact_probabilities.csv`.

Итоговый артефакт для LoM/Dis-LoM: `data/raw/<project>/<bug>/cia/impact_probabilities.csv`.

## Требования

- Linux/macOS (или Docker)
- Java 11
- Python 3.9+
- Perl + `cpanm`
- `git`, `svn`, `maven`, `gradle`
- Python-пакеты: `numpy`, `scikit-learn`

### Defects4J

В репозитории уже есть директория `defects4j/`, но её нужно инициализировать:

```bash
cd defects4j
cpanm --installdeps .
./init.sh
cd ..
```

Минимальные переменные окружения:

```bash
export D4J_HOME="$PWD/defects4j"
export PATH="$D4J_HOME/framework/bin:$PATH"
export JAVA_HOME="<путь-к-java11>"
export TZ="America/Los_Angeles"
```

`TZ=America/Los_Angeles` важен для воспроизводимости Defects4J.

## Быстрый старт в Docker

```bash
ROOT="$(git rev-parse --show-toplevel)"
docker build -t tcp .
docker run -it --rm \
  -v "$ROOT/data":/opt/project/data \
  -v "$ROOT/docs/lom_reports":/opt/project/docs/lom_reports \
  -w /opt/project \
  tcp
```

## Быстрый сценарий: один баг end-to-end

Пример для `Jsoup-93`.

```bash
# 1) checkout buggy/fixed версий
python3 scripts/checkout_versions.py Jsoup 93

# 2) подготовка CIA входов
python3 scripts/collect_modified_classes.py Jsoup 93
python3 scripts/generate_callgraph.py Jsoup 93

# 3) coverage + mutation
python3 scripts/run_gzoltar.py Jsoup 93
python3 scripts/run_major.py Jsoup 93

# 4) сборка Java-инструментов для CIA
(cd lom-study && ./gradlew installDist)

# 5) полный CIA pipeline (roc -> slicing -> markov)
python3 scripts/run_cia_pipeline.py --project Jsoup --bug 93

# 6) приоритизация
python3 scripts/run_lom.py --project Jsoup --bug 93 --mode lom --top 10
python3 scripts/run_lom.py --project Jsoup --bug 93 --mode dis-lom --top 10
python3 scripts/run_lom.py --project Jsoup --bug 93 --mode cov-clustering --top 10

# 7) APFD для LoM/Dis-LoM/CovClustering
python3 scripts/run_apfd_all.py

# 8) baseline TCP + APFD
python3 scripts/run_tcp_benchmarks.py --project Jsoup --bug 93
```

## Пакетный запуск по всем проектам из `config/projects.csv`

```bash
# coverage + mutation
python3 scripts/process_all_projects.py

# CIA
python3 scripts/run_cia_pipeline_all.py --skip-existing

# LoM / Dis-LoM / CovClustering
python3 scripts/run_lom_all.py --mode lom --skip-existing --output data/results/lom
python3 scripts/run_lom_all.py --mode dis-lom --skip-existing --output data/results/dis_lom
python3 scripts/run_lom_all.py --mode cov-clustering --skip-existing --output data/results/cov_clustering

# APFD + сводные отчёты
python3 scripts/run_apfd_all.py
python3 scripts/run_tcp_benchmarks.py
python3 scripts/analyze_apfd.py
python3 scripts/analyze_lom_alignment.py
```

Опционально сбор таймингов:

```bash
python3 scripts/run_lom_all.py --mode cov-clustering --timing-csv docs/lom_reports/timings.csv
python3 scripts/run_tcp_benchmarks.py --timing-csv docs/lom_reports/timings.csv
python3 scripts/summarize_timings.py --input docs/lom_reports/timings.csv
```

## Ключевые скрипты

| Скрипт | Назначение |
|---|---|
| `scripts/checkout_versions.py` | checkout Defects4J buggy/fixed |
| `scripts/run_gzoltar.py` | покрытие и экспорт `coverage/matrix.csv` |
| `scripts/run_major.py` | мутационный анализ и экспорт `mutants/*` |
| `scripts/generate_callgraph.py` | генерация `cia/callgraph.txt` |
| `scripts/run_cia_pipeline.py` | полный CIA для одного проекта |
| `scripts/run_cia_pipeline_all.py` | пакетный CIA |
| `scripts/run_lom.py` | single-run LoM/Dis-LoM/CovClustering |
| `scripts/run_lom_all.py` | batch-run LoM/Dis-LoM/CovClustering |
| `scripts/run_apfd_all.py` | APFD для LoM/Dis-LoM/CovClustering |
| `scripts/run_tcp_benchmarks.py` | TCP baselines + APFD |
| `scripts/analyze_apfd.py` | сводка LoM-family vs TCP |
| `scripts/analyze_lom_alignment.py` | coverage-to-impact matching статистика |

## Набор проектов

По умолчанию используются пары из `config/projects.csv`:

- `Jsoup-93`
- `Gson-18`
- `Csv-16`
- `JacksonDatabind-112`
- `JacksonXml-6`
- `Compress-47`
- `Time-27`
- `Codec-18`
- `JacksonCore-26`
- `Lang-65`


### Результаты приоритизации

- `lom_scores.csv`, `dis_lom_scores.csv`, `cov_clustering_scores.csv`
- формат: `rank,test,score`

### Отчёты

`docs/lom_reports/` содержит:
- `apfd_results.csv` — APFD для LoM/Dis-LoM/CovClustering
- `tcp_apfd_results.csv` — APFD TCP-baselines
- `apfd_summary.csv` — сравнение лучших режимов
- `apfd_method_mean.csv` — средний APFD по семействам
- `alignment_summary.csv` — статистика match coverage↔impact
- `timings.csv` — тайминги алгоритмов

## Структура репозитория

```text
tcp/
  README.md
  Dockerfile
  config/
    projects.csv
    major_excludes/
    mml/
    mml_filters/
  scripts/
    checkout_versions.py
    run_gzoltar.py
    run_major.py
    run_cia_pipeline.py
    run_cia_pipeline_all.py
    run_lom.py
    run_lom_all.py
    run_apfd_all.py
    run_tcp_benchmarks.py
    ...
  lom-study/
    src/main/java/dev/mpr/cia/
      RocExporterMain.java
      SootForwardSlicer.java
      AsmRocAnalyzer.java
      ...
    tcp/
      data_loader.py
      lom_algorithms.py
      cov_clustering.py
  tools/
    gzoltar/
    java-callgraph/
  data/
    raw/<project>/<bug>/{coverage,mutants,cia}/
    results/{lom,dis_lom,cov_clustering,tcp}/
  docs/lom_reports/
```

## Текущие результаты (из `docs/lom_reports`)

Средний APFD (`apfd_method_mean.csv`):

| Method | Mean APFD |
|---|---:|
| Dis-LoM | 0.9727 |
| LoM | 0.9336 |
| Additional | 0.8656 |
| Random-Avg | 0.8236 |
| Total | 0.8062 |


# Участники и вклад

Исходный TCP-pipeline разработан М. А. Руденко под руководством В. А. Пархоменко.

Данный репозиторий является расширением исходного pipeline.  
В рамках данной работы Е. В. Дубинин добавил и интегрировал два алгоритма приоритизации тестов:

- Bee Colony Prioritization;
- Geometric Combined Prioritization.

Также были изменены скрипты benchmark-запуска и обновлены отчёты с результатами сравнения по APFD.

# Гарантии
Разработчики не дают никаких гарантий по поводу использования данного программного обеспечения.

# Лицензия
Это программа открыта для использования и распростаняется под лицензией MIT.
