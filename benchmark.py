"""Compara AG, guloso e força bruta nas instâncias da base TSP do Kaggle."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from brute_force import solve_brute_force
from genetic import GeneticConfig, solve_genetic
from greedy_tsp import solve_greedy
from util import Instance, Solution, is_valid_route, load_cases, timed

# 8-10: primeiras cidades da instância de 20 (ótimo exato pela força bruta).
SIZES = (8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
BRUTE_FORCE_TIMEOUT_SECONDS = 600
# From this size on, (n-1)!/2 routes cannot finish in time, so the search is not run.
BRUTE_FORCE_SKIP_FROM = 16
ALGORITHMS = ("Genetic", "Greedy", "Brute force")
FIELDS = ("cities", "instance", "algorithm", "distance", "seconds", "status", "vs_greedy")
Row = dict[str, object]


def run_genetic(instance: Instance, config: GeneticConfig, seed: int) -> Row:
    return _row(instance, "Genetic",
                *timed(lambda: solve_genetic(instance.distances, config, seed=seed)))


def run_greedy(instance: Instance) -> Row:
    return _row(instance, "Greedy", *timed(lambda: solve_greedy(instance.distances)))


def run_brute_force(instance: Instance, timeout: float) -> Row:
    """Até 15 cidades busca com prazo; a partir de 16 não executa e registra timeout."""
    if instance.size >= BRUTE_FORCE_SKIP_FROM:
        return {"cities": instance.size, "instance": instance.label,
                "algorithm": "Brute force", "distance": None, "seconds": None,
                "status": "timeout"}
    return _row(instance, "Brute force",
                *timed(lambda: solve_brute_force(instance.distances, time_limit=timeout)))


def _row(instance: Instance, algorithm: str, solution: Solution, seconds: float) -> Row:
    if not is_valid_route(solution.route, instance.size):
        raise RuntimeError(f"{algorithm} devolveu uma rota inválida para {instance.label}")
    return {"cities": instance.size, "instance": instance.label, "algorithm": algorithm,
            "distance": solution.cost, "seconds": seconds, "status": solution.status}


def run_benchmarks(sizes=SIZES, config: GeneticConfig = GeneticConfig(), seed: int = 42,
                   brute_timeout: float = BRUTE_FORCE_TIMEOUT_SECONDS,
                   on_case_complete: Callable[[list[Row]], None] | None = None) -> list[Row]:
    """Executa as três abordagens em cada instância e devolve uma linha por execução."""
    if brute_timeout <= 0:
        raise ValueError("brute force timeout must be positive")
    results: list[Row] = []
    for instance in load_cases(tuple(sizes)):
        rows = [run_genetic(instance, config, seed + instance.size),
                run_greedy(instance),
                run_brute_force(instance, brute_timeout)]
        greedy_distance = rows[1]["distance"]
        for row in rows:
            row["vs_greedy"] = None if row["distance"] is None else \
                100 * (row["distance"] / greedy_distance - 1)
        results.extend(rows)
        if on_case_complete is not None:
            on_case_complete(results)
    return results


def _fmt(value, pattern: str) -> str:
    return "—" if value is None else format(value, pattern)


def save_results(results: list[Row], output_dir: Path,
                 brute_timeout: float = BRUTE_FORCE_TIMEOUT_SECONDS) -> None:
    """Grava a tabela Markdown, o CSV e o gráfico de comparação em docs/."""
    tables_dir = output_dir / "tables"
    graphs_dir = output_dir / "graphs"
    tables_dir.mkdir(parents=True, exist_ok=True)
    graphs_dir.mkdir(parents=True, exist_ok=True)
    with (tables_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    _save_markdown(results, tables_dir / "benchmark.md", brute_timeout)
    _save_chart(results, graphs_dir / "comparison.png")


def _save_markdown(results: list[Row], path: Path, brute_timeout: float) -> None:
    lines = ["# Resultados do benchmark", "",
             "| Cidades | Instância | Algoritmo | Distância percorrida | Tempo (s) | Status "
             "| vs guloso (%) |",
             "| ---: | :--- | :--- | ---: | ---: | :--- | ---: |"]
    for row in results:
        lines.append(f'| {row["cities"]} | {row["instance"]} | {row["algorithm"]} | '
                     f'{_fmt(row["distance"], ".2f")} | {_fmt(row["seconds"], ".4f")} | '
                     f'{row["status"]} | {_fmt(row["vs_greedy"], "+.1f")} |')
    lines.extend([
        "",
        "Instância `#id` é o `instance_id` da base do Kaggle; `(primeiras k)` indica a "
        "sub-instância com as k primeiras cidades. `vs guloso`: diferença de distância em "
        "relação ao guloso (negativo = rota menor). `ok`: execução concluída (na força "
        f"bruta, ótimo exato). `timeout`: a partir de {BRUTE_FORCE_SKIP_FROM} cidades a força "
        "bruta não é executada, pois as `(n-1)!/2` rotas não terminariam no prazo; entre 11 e "
        f"{BRUTE_FORCE_SKIP_FROM - 1} cidades, é a melhor rota encontrada em até "
        f"{brute_timeout:g} s.",
        ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _save_chart(results: list[Row], path: Path) -> None:
    sizes = sorted({row["cities"] for row in results})
    # Evenly spaced positions keep the 8/9/10 prefixes readable next to 20..100.
    position = {size: index for index, size in enumerate(sizes)}
    figure, (quality, runtime) = plt.subplots(1, 2, figsize=(12, 5))
    styles = {"Genetic": ("tab:blue", "o", "-"), "Greedy": ("tab:green", "s", "-"),
              "Brute force": ("tab:red", "*", "none")}
    for algorithm in ALGORITHMS:
        rows = sorted((row for row in results
                       if row["algorithm"] == algorithm and row["distance"] is not None),
                      key=lambda row: row["cities"])
        if not rows:
            continue
        color, marker, line = styles[algorithm]
        label = "Brute force (exact)" if algorithm == "Brute force" else algorithm
        xs = [position[row["cities"]] for row in rows]
        size = 12 if algorithm == "Brute force" else 6
        quality.plot(xs, [row["distance"] for row in rows], color=color, marker=marker,
                     linestyle=line, markersize=size, label=label)
        runtime.plot(xs, [row["seconds"] for row in rows], color=color, marker=marker,
                     linestyle=line, markersize=size, label=label)
    quality.set(title="Tour distance (lower is better)", xlabel="Cities", ylabel="Distance")
    runtime.set(title="Execution time (log scale)", xlabel="Cities", ylabel="Seconds",
                yscale="log")
    for axis in (quality, runtime):
        axis.set_xticks(range(len(sizes)), labels=[str(size) for size in sizes])
        axis.grid(alpha=0.3)
        axis.legend()
    figure.suptitle("TSP on the Kaggle TSPLIB-style dataset | 8-10 cities: prefixes of the "
                    f"20-city instance | brute force not run from {BRUTE_FORCE_SKIP_FROM} cities")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = GeneticConfig()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES),
                        help="cidades por caso; < 20 usa as primeiras cidades da instância "
                             "de 20 (padrão: 8 9 10 20 30 ... 100)")
    parser.add_argument("--generations", type=int, default=defaults.generations)
    parser.add_argument("--population", type=int, default=defaults.population_size)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--brute-timeout", type=float, default=BRUTE_FORCE_TIMEOUT_SECONDS,
                        help="prazo da força bruta até 15 cidades (padrão: 600 s); a partir "
                             "de 16 ela não é executada e é registrada como timeout")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "docs")
    args = parser.parse_args()

    try:
        config = GeneticConfig(population_size=args.population, generations=args.generations,
                               tournament_size=min(defaults.tournament_size, args.population),
                               elite_size=min(defaults.elite_size, args.population - 1))
    except ValueError as exc:
        parser.error(str(exc))

    print(f'{"Cidades":>7} | {"Instância":<18} | {"Algoritmo":<11} | {"Distância":>10} | '
          f'{"Tempo (s)":>9} | {"vs guloso %":>11} | Status', flush=True)

    def record_case(rows: list[Row]) -> None:
        save_results(rows, args.output, args.brute_timeout)
        for row in rows[-len(ALGORITHMS):]:
            print(f'{row["cities"]:>7} | {row["instance"]:<18} | {row["algorithm"]:<11} | '
                  f'{_fmt(row["distance"], ".2f"):>10} | {_fmt(row["seconds"], ".4f"):>9} | '
                  f'{_fmt(row["vs_greedy"], "+.1f"):>11} | {row["status"]}', flush=True)

    try:
        run_benchmarks(sizes=tuple(dict.fromkeys(args.sizes)), config=config, seed=args.seed,
                       brute_timeout=args.brute_timeout, on_case_complete=record_case)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Tabelas em {args.output / 'tables'} e gráfico em {args.output / 'graphs'}")


if __name__ == "__main__":
    main()
