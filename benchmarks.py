"""Roda todas as abordagens e gera GIFs, tabelas e gráficos em docs/.

Uso: python benchmarks.py                        # tudo (~30 min)
     python benchmarks.py --only benchmark gifs  # só o benchmark principal e os GIFs
     python benchmarks.py --only E8              # um experimento específico
     python benchmarks.py --docs-only            # refaz tabelas e gráficos dos CSVs salvos

Etapas:
  benchmark  AG, guloso e força bruta em 8, 9, 10 e 20..100 cidades (uma instância por tamanho)
  gifs       animações de cada abordagem (10, 20, 50 e 100 cidades)
  E1  Crescimento da força bruta (4 a 12 cidades) e projeção de O(n!)
  E2  Gap até o ótimo exato em 20 sub-instâncias de 10 cidades
  E3  Os 81 tamanhos da base (20 a 100 cidades)
  E4  5 instâncias por tamanho (20, 30, ..., 100)
  E5  Guloso em todas as 2.783 instâncias da base
  E6  AG com 10 sementes e curva de convergência
  E7  101 a 149 cidades (segundo CSV do Kaggle)
  E8  TSPLIB clássico (48 a 442 cidades) com ótimo publicado
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import docs
from bruteforce import DEFAULT_TIMEOUT_SECONDS, SKIP_FROM_CITIES, route_count, solve_brute_force
from genetic import GeneticConfig, solve_genetic
from greedy import solve_greedy
from utils import (DATASET_MIN_CITIES, TSPLIB_INSTANCES, TSPLIB_OPTIMA, Instance, Route,
                   Solution, is_valid_route, iter_instances, load_cases, load_extra_instances,
                   load_instance_groups, load_instances, load_tsplib, timed)

# 8-10: primeiras cidades da instância de 20 (ótimo exato pela força bruta).
SIZES = (8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
GIF_SIZES = (10, 20, 50, 100)
GIF_FRAMES = 18
MAX_BRUTE_FORCE_GIF_CITIES = 10
FIELDS = ("experiment", "dataset", "instance", "cities", "algorithm", "seed", "distance",
          "seconds", "status", "reference", "gap_reference", "vs_greedy")
CONVERGENCE_FIELDS = ("instance", "cities", "seed", "generation", "best")
KAGGLE, KAGGLE_EXTRA, TSPLIB = "Kaggle tsp_dataset", "Kaggle tsp_instances", "TSPLIB"

BRUTE_GROWTH_SIZES = tuple(range(4, 13))
# E1 needs 12 cities (~20 M routes) to finish, so its deadline is far above the default.
BRUTE_GROWTH_TIMEOUT_SECONDS = 3600
EXACT_GAP_INSTANCES = 20
EXACT_GAP_CITIES = 10
DECADE_SIZES = tuple(range(20, 101, 10))
INSTANCES_PER_SIZE = 5
SEED_SIZES = (20, 50, 100)
SEEDS = tuple(range(10))
EXTRA_MIN_CITIES = 101
Row = dict[str, object]


@dataclass(frozen=True)
class Settings:
    config: GeneticConfig
    seed: int
    sizes: tuple[int, ...]
    gif_sizes: tuple[int, ...]
    brute_timeout: float
    output: Path


# ---------------------------------------------------------------- execução de cada abordagem

def run_genetic(instance: Instance, config: GeneticConfig, seed: int) -> Row:
    row = _row(instance, "Genetic",
               *timed(lambda: solve_genetic(instance.distances, config, seed=seed)))
    return {**row, "seed": seed}


def run_greedy(instance: Instance) -> Row:
    return _row(instance, "Greedy", *timed(lambda: solve_greedy(instance.distances)))


def run_brute_force(instance: Instance, timeout: float) -> Row:
    """Até 15 cidades busca com prazo; a partir de 16 não executa e registra timeout."""
    if instance.size >= SKIP_FROM_CITIES:
        return {"cities": instance.size, "instance": instance.label, "algorithm": "Brute force",
                "distance": None, "seconds": None, "status": "timeout"}
    return _row(instance, "Brute force",
                *timed(lambda: solve_brute_force(instance.distances, time_limit=timeout)))


def _row(instance: Instance, algorithm: str, solution: Solution, seconds: float) -> Row:
    if not is_valid_route(solution.route, instance.size):
        raise RuntimeError(f"{algorithm} devolveu uma rota inválida para {instance.label}")
    return {"cities": instance.size, "instance": instance.label, "algorithm": algorithm,
            "distance": solution.cost, "seconds": seconds, "status": solution.status}


def run_all(experiment: str, dataset: str, instance: Instance, settings: Settings, seed: int,
            reference: float | None = None, with_brute: bool = True,
            brute_timeout: float | None = None) -> list[Row]:
    """AG, guloso e (opcionalmente) força bruta na mesma instância, com as comparações."""
    rows = [run_genetic(instance, settings.config, seed), run_greedy(instance)]
    if with_brute:
        brute = run_brute_force(instance, brute_timeout or settings.brute_timeout)
        rows.append(brute)
        if reference is None and brute["status"] == "ok":
            reference = brute["distance"]  # ótimo exato
    return [annotate(row, experiment, dataset, reference, rows[1]["distance"]) for row in rows]


def annotate(row: Row, experiment: str, dataset: str, reference: float | None,
             greedy_distance: float) -> Row:
    distance = row["distance"]
    has_distance = distance is not None
    return {
        **row, "experiment": experiment, "dataset": dataset, "seed": row.get("seed"),
        "reference": reference,
        "gap_reference": 100 * (distance / reference - 1) if has_distance and reference else None,
        "vs_greedy": 100 * (distance / greedy_distance - 1) if has_distance else None,
    }


def log(message: str) -> None:
    print(message, flush=True)


def _fmt(value, pattern: str) -> str:
    return "—" if value is None else format(value, pattern)


# ---------------------------------------------------------------- benchmark principal e GIFs

def step_benchmark(settings: Settings) -> list[Row]:
    log(f'{"Cidades":>7} | {"Instância":<18} | {"Algoritmo":<11} | {"Distância":>10} | '
        f'{"Tempo (s)":>9} | {"vs guloso %":>11} | Status')
    rows: list[Row] = []
    for instance in load_cases(settings.sizes):
        case = run_all("benchmark", KAGGLE, instance, settings, settings.seed + instance.size)
        rows += case
        for row in case:
            log(f'{row["cities"]:>7} | {row["instance"]:<18} | {row["algorithm"]:<11} | '
                f'{_fmt(row["distance"], ".2f"):>10} | {_fmt(row["seconds"], ".4f"):>9} | '
                f'{_fmt(row["vs_greedy"], "+.1f"):>11} | {row["status"]}')
    return rows


def step_gifs(settings: Settings) -> list[Row]:
    for instance in load_cases(settings.gif_sizes):
        edges: list[tuple[int, int]] = []
        greedy = solve_greedy(instance.distances, on_edge=lambda a, b: edges.append((a, b)))
        docs.render_greedy_gif(instance, edges, greedy.cost, settings.output, GIF_FRAMES)

        history: list[tuple[int, Route, float]] = []
        solve_genetic(instance.distances, settings.config, seed=settings.seed + instance.size,
                      on_generation=lambda g, route, cost: history.append((g, route, cost)))
        docs.render_genetic_gif(instance, history, settings.config.generations,
                                settings.output, GIF_FRAMES)

        if instance.size > MAX_BRUTE_FORCE_GIF_CITIES:
            log(f"GIF de força bruta ignorado para {instance.size} cidades: "
                f"(n-1)!/2 = {route_count(instance.size):.3g} rotas.")
            continue
        improvements: list[tuple[int, Route, float]] = []
        solve_brute_force(instance.distances, on_improvement=lambda count, route, cost:
                          improvements.append((count, route, cost)))
        docs.render_brute_force_gif(instance, improvements, settings.output, GIF_FRAMES)
    return []


# ---------------------------------------------------------------- experimentos E1-E8

def e1_brute_growth(settings: Settings) -> list[Row]:
    base = load_instances([DATASET_MIN_CITIES])[DATASET_MIN_CITIES]
    rows = []
    for size in BRUTE_GROWTH_SIZES:
        rows += run_all("E1", KAGGLE, base.prefix(size), settings, settings.seed + size,
                        brute_timeout=BRUTE_GROWTH_TIMEOUT_SECONDS)
        log(f"E1 n={size}: força bruta {rows[-1]['seconds']:.3f}s ({route_count(size):,} rotas)")
    return rows


def e2_exact_gap(settings: Settings) -> list[Row]:
    group = load_instance_groups([DATASET_MIN_CITIES], EXACT_GAP_INSTANCES)[DATASET_MIN_CITIES]
    rows = []
    for instance in group:
        rows += run_all("E2", KAGGLE, instance.prefix(EXACT_GAP_CITIES), settings,
                        settings.seed + instance.instance_id)
        log(f"E2 {rows[-1]['instance']}: ótimo {rows[-1]['distance']:.2f}")
    return rows


def e3_all_sizes(settings: Settings) -> list[Row]:
    rows = []
    for size, instance in sorted(load_instances(range(20, 101)).items()):
        rows += run_all("E3", KAGGLE, instance, settings, settings.seed + size, with_brute=False)
        log(f"E3 n={size}: AG {rows[-2]['vs_greedy']:+.1f}% vs guloso")
    return rows


def e4_instance_variability(settings: Settings) -> list[Row]:
    rows = []
    for size, group in sorted(load_instance_groups(DECADE_SIZES, INSTANCES_PER_SIZE).items()):
        for instance in group:
            rows += run_all("E4", KAGGLE, instance, settings,
                            settings.seed + instance.instance_id, with_brute=False)
        log(f"E4 n={size}: {len(group)} instâncias")
    return rows


def e5_greedy_full_dataset(settings: Settings) -> list[Row]:
    rows = []
    for instance in iter_instances():
        greedy = run_greedy(instance)
        rows.append(annotate(greedy, "E5", KAGGLE, None, greedy["distance"]))
        if len(rows) % 500 == 0:
            log(f"E5 {len(rows)} instâncias")
    return rows


def e6_ga_seeds(settings: Settings) -> list[Row]:
    rows, convergence = [], []
    for size, instance in sorted(load_instances(SEED_SIZES).items()):
        greedy = run_greedy(instance)
        rows.append(annotate(greedy, "E6", KAGGLE, None, greedy["distance"]))
        for run_seed in SEEDS:
            history: list[float] = []
            solution, seconds = timed(lambda: solve_genetic(
                instance.distances, settings.config, seed=run_seed,
                on_generation=lambda g, route, cost: history.append(cost)))
            convergence += [{"instance": instance.label, "cities": size, "seed": run_seed,
                             "generation": g, "best": cost}
                            for g, cost in enumerate(history, start=1)]
            row = {"cities": size, "instance": instance.label, "algorithm": "Genetic",
                   "distance": solution.cost, "seconds": seconds, "status": solution.status,
                   "seed": run_seed}
            rows.append(annotate(row, "E6", KAGGLE, None, greedy["distance"]))
        log(f"E6 n={size}: {len(SEEDS)} sementes")
    docs.write_csv(settings.output / "data" / "E6_convergence.csv", convergence,
                   CONVERGENCE_FIELDS)
    return rows


def e7_kaggle_extra(settings: Settings) -> list[Row]:
    rows = []
    for instance in load_extra_instances(EXTRA_MIN_CITIES):
        rows += run_all("E7", KAGGLE_EXTRA, instance, settings, settings.seed + instance.size,
                        with_brute=False)
        log(f"E7 {instance.label} n={instance.size}: AG {rows[-2]['vs_greedy']:+.1f}%")
    return rows


def e8_tsplib(settings: Settings) -> list[Row]:
    rows = []
    for name in TSPLIB_INSTANCES:
        instance = load_tsplib(name)
        rows += run_all("E8", TSPLIB, instance, settings, settings.seed + instance.size,
                        reference=TSPLIB_OPTIMA[name], with_brute=False)
        log(f"E8 {name}: guloso {rows[-1]['gap_reference']:+.1f}%, "
            f"AG {rows[-2]['gap_reference']:+.1f}% do ótimo")
    return rows


STEPS: dict[str, Callable[[Settings], list[Row]]] = {
    "benchmark": step_benchmark, "gifs": step_gifs,
    "E1": e1_brute_growth, "E2": e2_exact_gap, "E3": e3_all_sizes,
    "E4": e4_instance_variability, "E5": e5_greedy_full_dataset, "E6": e6_ga_seeds,
    "E7": e7_kaggle_extra, "E8": e8_tsplib,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=list(STEPS), default=list(STEPS),
                        help="etapas a executar (padrão: todas)")
    parser.add_argument("--docs-only", action="store_true",
                        help="não executa nada; refaz tabelas, gráficos e docs/README.md")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES),
                        help="cidades do benchmark principal; < 20 usa as primeiras cidades da "
                             "instância de 20 (padrão: 8 9 10 20 30 ... 100)")
    parser.add_argument("--gif-sizes", nargs="+", type=int, default=list(GIF_SIZES))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--brute-timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                        help=f"prazo da força bruta até {SKIP_FROM_CITIES - 1} cidades "
                             f"(padrão: {DEFAULT_TIMEOUT_SECONDS} s)")
    parser.add_argument("--output", type=Path, default=docs.DOCS_DIR)
    args = parser.parse_args()
    if args.brute_timeout <= 0:
        parser.error("--brute-timeout deve ser positivo")

    settings = Settings(config=GeneticConfig(), seed=args.seed,
                        sizes=tuple(dict.fromkeys(args.sizes)),
                        gif_sizes=tuple(dict.fromkeys(args.gif_sizes)),
                        brute_timeout=args.brute_timeout, output=args.output)
    if not args.docs_only:
        for name in args.only:
            log(f"== {name}")
            try:
                rows, seconds = timed(lambda: STEPS[name](settings))
            except ValueError as exc:
                parser.error(str(exc))
            if rows:
                docs.write_csv(settings.output / "data" / f"{name}.csv", rows, FIELDS)
            log(f"== {name} concluído em {seconds / 60:.1f} min ({len(rows)} execuções)")
    readme = docs.build_docs(settings.output, settings.brute_timeout)
    log(f"Tabelas, gráficos e resumo em {readme.parent} (veja {readme.name})")


if __name__ == "__main__":
    main()
