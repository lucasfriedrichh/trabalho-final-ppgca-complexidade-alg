"""Força bruta: avalia todos os circuitos hamiltonianos e devolve o menor.

A cidade 0 é fixada como início e cada ciclo é avaliado em apenas um sentido
(a segunda cidade tem índice menor que a última), pois a matriz é simétrica.
São (n-1)!/2 rotas: tempo O(n!), inviável a partir de poucas dezenas de cidades.
"""

from __future__ import annotations

import itertools
import math
import time
from typing import Callable

from utils import Matrix, Route, Solution

# Checking the clock on every permutation would dominate the loop cost.
DEADLINE_CHECK_EVERY = 4096
DEFAULT_TIMEOUT_SECONDS = 600
# From this size on, (n-1)!/2 routes cannot finish in time, so the search is not run.
SKIP_FROM_CITIES = 16


def solve_brute_force(distances: Matrix, time_limit: float | None = None,
                      on_improvement: Callable[[int, Route, float], None] | None = None
                      ) -> Solution:
    """Busca exaustiva; com `time_limit`, para no prazo e marca status "timeout"."""
    size = len(distances)
    if size < 2:
        raise ValueError("A força bruta precisa de pelo menos 2 cidades")
    if time_limit is not None and time_limit <= 0:
        raise ValueError("time_limit deve ser positivo")
    deadline = None if time_limit is None else time.perf_counter() + time_limit
    start_row = distances[0]
    best_route: Route = tuple(range(size))
    best_cost = math.inf
    evaluated = 0

    for index, tail in enumerate(itertools.permutations(range(1, size)), start=1):
        if tail[0] > tail[-1]:
            continue  # o mesmo ciclo no sentido inverso já foi avaliado
        evaluated += 1
        cost = start_row[tail[0]] + start_row[tail[-1]]
        for current, following in zip(tail, tail[1:]):
            cost += distances[current][following]
        if cost < best_cost:
            best_cost, best_route = cost, (0, *tail)
            if on_improvement is not None:
                on_improvement(evaluated, best_route, best_cost)
        if deadline is not None and index % DEADLINE_CHECK_EVERY == 0 \
                and time.perf_counter() >= deadline:
            return Solution(best_route, best_cost, "timeout")
    return Solution(best_route, best_cost)


def route_count(size: int) -> int:
    """Número de circuitos distintos avaliados: (n-1)!/2 (1 para n <= 2)."""
    return max(1, math.factorial(size - 1) // 2)
