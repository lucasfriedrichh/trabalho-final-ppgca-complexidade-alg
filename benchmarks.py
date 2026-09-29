"""Roda as três abordagens em 5 execuções e gera GIFs, tabelas e gráficos em docs/.

Uso: python benchmarks.py
     python benchmarks.py --sizes 8 10 30 60 90 --seed 7

Cada execução usa uma quantidade diferente de cidades. Nela, força bruta, genético
e guloso resolvem a mesma instância; são comparados o tempo de execução, a
distância total obtida e a diferença entre as abordagens. Tamanhos menores que
20 usam as primeiras cidades da instância de 20 da base (ótimo exato pela força bruta).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import docs
from bruteforce import DEFAULT_TIMEOUT_SECONDS, SKIP_FROM_CITIES, solve_brute_force
from genetic import GeneticConfig, solve_genetic
from greedy import solve_greedy
from utils import Instance, Route, Solution, is_valid_route, load_cases, timed

# 8 and 12: first cities of the 20-city instance, where brute force gives the exact optimum.
SIZES = (8, 12, 20, 50, 100)
# The GIF only samples the improvements, so any brute force run that finishes can be animated.
MAX_BRUTE_FORCE_GIF_CITIES = SKIP_FROM_CITIES - 1
FIELDS = ("execution", "cities", "instance", "algorithm", "distance", "seconds", "status")
Row = dict[str, object]


@dataclass(frozen=True)
class Settings:
    config: GeneticConfig
    seed: int
    brute_timeout: float
    output: Path


def _row(execution: int, instance: Instance, algorithm: str, solution: Solution | None,
         seconds: float | None) -> Row:
    if solution is not None and not is_valid_route(solution.route, instance.size):
        raise RuntimeError(f"{algorithm} devolveu uma rota inválida para {instance.label}")
    return {"execution": execution, "cities": instance.size, "instance": instance.label,
            "algorithm": algorithm, "seconds": seconds,
            "distance": None if solution is None else solution.cost,
            "status": "timeout" if solution is None else solution.status}


def run_brute_force(execution: int, instance: Instance, settings: Settings) -> Row:
    """Até 15 cidades busca com prazo; a partir de 16 não executa e registra timeout."""
    if instance.size >= SKIP_FROM_CITIES:
        return _row(execution, instance, "Brute force", None, None)
    improvements: list[tuple[int, Route, float]] = []
    solution, seconds = timed(lambda: solve_brute_force(
        instance.distances, time_limit=settings.brute_timeout,
        on_improvement=lambda count, route, cost: improvements.append((count, route, cost))))
    if instance.size <= MAX_BRUTE_FORCE_GIF_CITIES and solution.status == "ok":
        docs.render_brute_force_gif(instance, improvements, settings.output)
    return _row(execution, instance, "Brute force", solution, seconds)


def run_genetic(execution: int, instance: Instance, settings: Settings) -> Row:
    history: list[tuple[int, Route, float]] = []
    solution, seconds = timed(lambda: solve_genetic(
        instance.distances, settings.config, seed=settings.seed + instance.size,
        on_generation=lambda generation, route, cost: history.append((generation, route, cost))))
    docs.render_genetic_gif(instance, history, settings.config.generations, settings.output)
    return _row(execution, instance, "Genetic", solution, seconds)


def run_greedy(execution: int, instance: Instance, settings: Settings) -> Row:
    edges: list[tuple[int, int]] = []
    solution, seconds = timed(lambda: solve_greedy(
        instance.distances, on_edge=lambda a, b: edges.append((a, b))))
    docs.render_greedy_gif(instance, edges, solution.cost, settings.output)
    return _row(execution, instance, "Greedy", solution, seconds)


def run_execution(execution: int, instance: Instance, settings: Settings) -> list[Row]:
    """As três abordagens na mesma instância."""
    return [runner(execution, instance, settings)
            for runner in (run_brute_force, run_genetic, run_greedy)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES),
                        help="cidades de cada execução (padrão: 8 12 20 50 100)")
    parser.add_argument("--seed", type=int, default=42, help="semente do genético")
    parser.add_argument("--brute-timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                        help=f"prazo da força bruta até {SKIP_FROM_CITIES - 1} cidades "
                             f"(padrão: {DEFAULT_TIMEOUT_SECONDS} s)")
    parser.add_argument("--output", type=Path, default=docs.DOCS_DIR)
    args = parser.parse_args()
    if args.brute_timeout <= 0:
        parser.error("--brute-timeout deve ser positivo")
    sizes = tuple(dict.fromkeys(args.sizes))
    try:
        instances = load_cases(sizes)
    except ValueError as exc:
        parser.error(str(exc))

    settings = Settings(GeneticConfig(), args.seed, args.brute_timeout, args.output)
    rows: list[Row] = []
    for execution, instance in enumerate(instances, start=1):
        print(f"== Execução {execution}: {instance.size} cidades ({instance.label})", flush=True)
        rows += run_execution(execution, instance, settings)
    docs.write_csv(settings.output / "data" / "results.csv", rows, FIELDS)
    readme = docs.build_docs(settings.output, settings.brute_timeout)
    print(f"Comparação em {readme}", flush=True)


if __name__ == "__main__":
    main()
