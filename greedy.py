"""Guloso de arestas (greedy edge) para o caixeiro viajante.

Ordena todas as arestas pela distância e adiciona a menor que ainda mantém
uma solução parcial válida: nenhuma cidade com grau maior que 2 e nenhum
ciclo antes de incluir todas as cidades (verificado com union-find).
Após n-1 arestas, o caminho resultante é fechado ligando suas duas pontas.
Tempo O(n² log n), dominado pela ordenação das n(n-1)/2 arestas.
"""

from __future__ import annotations

from typing import Callable

from utils import Matrix, Route, Solution, route_cost


def solve_greedy(distances: Matrix,
                 on_edge: Callable[[int, int], None] | None = None) -> Solution:
    """Constrói o circuito aresta a aresta; `on_edge` recebe cada aresta aceita."""
    size = len(distances)
    if size < 2:
        raise ValueError("O guloso precisa de pelo menos 2 cidades")
    edges = sorted((distances[i][j], i, j) for i in range(size) for j in range(i + 1, size))
    degree = [0] * size
    parent = list(range(size))
    neighbours: list[list[int]] = [[] for _ in range(size)]

    def root(city: int) -> int:
        while parent[city] != city:
            parent[city] = parent[parent[city]]
            city = parent[city]
        return city

    accepted = 0
    for _, i, j in edges:
        if accepted == size - 1:
            break
        if degree[i] == 2 or degree[j] == 2:
            continue
        root_i, root_j = root(i), root(j)
        if root_i == root_j:
            continue  # fecharia um ciclo antes de visitar todas as cidades
        parent[root_i] = root_j
        degree[i] += 1
        degree[j] += 1
        neighbours[i].append(j)
        neighbours[j].append(i)
        accepted += 1
        if on_edge is not None:
            on_edge(i, j)

    route = _walk_path(neighbours)
    if on_edge is not None and size > 2:
        on_edge(route[-1], route[0])
    return Solution(route, route_cost(route, distances))


def _walk_path(neighbours: list[list[int]]) -> Route:
    """Percorre o caminho hamiltoniano a partir de uma de suas pontas."""
    start = next(city for city, adjacent in enumerate(neighbours) if len(adjacent) < 2)
    route = [start]
    previous = -1
    while len(route) < len(neighbours):
        current = route[-1]
        following = next(city for city in neighbours[current] if city != previous)
        previous = current
        route.append(following)
    return tuple(route)
