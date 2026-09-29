"""Testes das funções compartilhadas e das três abordagens (python -m unittest discover tests)."""

import csv
import itertools
import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from brute_force import route_count, solve_brute_force
from genetic import GeneticConfig, inversion_mutation, order_crossover, solve_genetic
from greedy_tsp import solve_greedy
from util import is_valid_route, load_cases, load_instances, parse_instance, route_cost


def matrix_for(points):
    return tuple(tuple(math.dist(a, b) for b in points) for a in points)


def circle(size):
    """Pontos num círculo: o ótimo é o polígono convexo, na ordem angular."""
    return [(math.cos(2 * math.pi * i / size), math.sin(2 * math.pi * i / size))
            for i in range(size)]


def shuffled_circle(size, seed):
    points = circle(size)
    random.Random(seed).shuffle(points)
    return points


def random_points(size, seed):
    rng = random.Random(seed)
    return [(rng.uniform(0, 100), rng.uniform(0, 100)) for _ in range(size)]


def exhaustive_optimum(distances):
    """Oráculo independente: todas as permutações, sem fixar cidade nem sentido."""
    return min(route_cost(route, distances)
               for route in itertools.permutations(range(len(distances))))


def csv_row(instance_id, points, **overrides):
    row = {"instance_id": str(instance_id), "num_cities": str(len(points)),
           "city_coordinates": json.dumps(points),
           "distance_matrix": json.dumps([list(line) for line in matrix_for(points)]),
           "best_route": "Route_0", "total_distance": "0"}
    row.update(overrides)
    return row


class UtilTests(unittest.TestCase):
    def test_route_cost_includes_return_to_start(self):
        square = matrix_for([(0, 0), (1, 0), (1, 1), (0, 1)])
        self.assertAlmostEqual(route_cost((0, 1, 2, 3), square), 4)
        self.assertAlmostEqual(route_cost((0, 2, 1, 3), square), 2 + 2 * math.sqrt(2))

    def test_is_valid_route_requires_each_city_once(self):
        self.assertTrue(is_valid_route((2, 0, 1), 3))
        self.assertFalse(is_valid_route((0, 0, 1), 3))
        self.assertFalse(is_valid_route((0, 1), 3))

    def test_parse_instance_rejects_inconsistent_rows(self):
        points = [[0, 0], [3, 0], [0, 4]]
        self.assertEqual(parse_instance(csv_row(7, points)).size, 3)
        with self.assertRaisesRegex(ValueError, "coordenadas"):
            parse_instance(csv_row(7, points, num_cities="4"))
        asymmetric = [[0, 1, 2], [9, 0, 3], [2, 3, 0]]
        with self.assertRaisesRegex(ValueError, "simétrica"):
            parse_instance(csv_row(7, points, distance_matrix=json.dumps(asymmetric)))

    def test_prefix_keeps_first_cities_and_distances(self):
        instance = parse_instance(csv_row(5, random_points(6, 1)))
        prefix = instance.prefix(4)
        self.assertEqual(prefix.size, 4)
        self.assertEqual(prefix.distances[3][1], instance.distances[3][1])
        self.assertEqual(prefix.label, "#5 (primeiras 4)")
        with self.assertRaises(ValueError):
            instance.prefix(7)

    def test_load_instances_and_cases_pick_lowest_id_per_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tsp_dataset.csv"
            rows = [csv_row(9, random_points(20, 1)), csv_row(3, random_points(20, 2)),
                    csv_row(4, random_points(21, 3))]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            instances = load_instances({20, 21}, path)
            self.assertEqual(instances[20].instance_id, 3)
            cases = load_cases((8, 21), path)
            self.assertEqual([case.size for case in cases], [8, 21])
            self.assertEqual(cases[0].label, "#3 (primeiras 8)")
            with self.assertRaisesRegex(ValueError, "22"):
                load_instances({22}, path)


class BruteForceTests(unittest.TestCase):
    def test_matches_exhaustive_oracle(self):
        for seed in range(3):
            distances = matrix_for(random_points(7, seed))
            solution = solve_brute_force(distances)
            self.assertEqual(solution.status, "ok")
            self.assertTrue(is_valid_route(solution.route, 7))
            self.assertAlmostEqual(solution.cost, exhaustive_optimum(distances))
            self.assertAlmostEqual(solution.cost, route_cost(solution.route, distances))

    def test_finds_convex_polygon_on_circle(self):
        solution = solve_brute_force(matrix_for(shuffled_circle(8, 1)))
        self.assertAlmostEqual(solution.cost, 16 * math.sin(math.pi / 8))

    def test_reports_timeout_with_best_route_so_far(self):
        distances = matrix_for(random_points(12, 4))
        solution = solve_brute_force(distances, time_limit=0.05)
        self.assertEqual(solution.status, "timeout")
        self.assertTrue(is_valid_route(solution.route, 12))

    def test_route_count_and_small_inputs(self):
        self.assertEqual(route_count(10), math.factorial(9) // 2)
        self.assertAlmostEqual(solve_brute_force(matrix_for([(0, 0), (3, 4)])).cost, 10)
        with self.assertRaises(ValueError):
            solve_brute_force(((0.0,),))


class GreedyTests(unittest.TestCase):
    def test_builds_valid_tour_and_reports_every_edge(self):
        distances = matrix_for(random_points(30, 5))
        edges = []
        solution = solve_greedy(distances, on_edge=lambda a, b: edges.append((a, b)))
        self.assertTrue(is_valid_route(solution.route, 30))
        self.assertEqual(len(edges), 30)
        self.assertAlmostEqual(solution.cost, sum(distances[a][b] for a, b in edges))

    def test_is_optimal_on_convex_polygon(self):
        solution = solve_greedy(matrix_for(shuffled_circle(12, 6)))
        self.assertAlmostEqual(solution.cost, 24 * math.sin(math.pi / 12))

    def test_never_beats_the_optimum(self):
        distances = matrix_for(random_points(8, 7))
        optimum = solve_brute_force(distances).cost
        self.assertGreaterEqual(solve_greedy(distances).cost, optimum - 1e-9)


class GeneticTests(unittest.TestCase):
    def test_operators_keep_permutations(self):
        rng = random.Random(1)
        first = tuple(rng.sample(range(15), 15))
        second = tuple(rng.sample(range(15), 15))
        for _ in range(200):
            self.assertTrue(is_valid_route(order_crossover(first, second, rng), 15))
            self.assertTrue(is_valid_route(inversion_mutation(first, rng), 15))

    def test_crossover_keeps_a_segment_of_the_first_parent(self):
        first = tuple(range(10))
        second = tuple(reversed(range(10)))
        child = order_crossover(first, second, random.Random(3))
        kept = [i for i in range(10) if child[i] == first[i]]
        self.assertTrue(kept)
        self.assertEqual(kept, list(range(kept[0], kept[-1] + 1)))

    def test_is_deterministic_for_a_seed_and_reaches_small_optimum(self):
        distances = matrix_for(random_points(8, 8))
        config = GeneticConfig(population_size=40, generations=150)
        first = solve_genetic(distances, config, seed=11)
        second = solve_genetic(distances, config, seed=11)
        self.assertEqual(first, second)
        self.assertTrue(is_valid_route(first.route, 8))
        self.assertAlmostEqual(first.cost, solve_brute_force(distances).cost)

    def test_reports_each_generation(self):
        distances = matrix_for(random_points(12, 9))
        history = []
        solution = solve_genetic(distances, GeneticConfig(population_size=20, generations=15),
                                 seed=2, on_generation=lambda g, r, c: history.append((g, c)))
        self.assertEqual([g for g, _ in history], list(range(1, 16)))
        self.assertAlmostEqual(history[-1][1], solution.cost)
        self.assertTrue(all(b <= a + 1e-9 for (_, a), (_, b) in zip(history, history[1:])))

    def test_rejects_invalid_config(self):
        with self.assertRaises(ValueError):
            GeneticConfig(population_size=3)
        with self.assertRaises(ValueError):
            GeneticConfig(mutation_rate=1.5)
        with self.assertRaises(ValueError):
            GeneticConfig(population_size=10, elite_size=10)


if __name__ == "__main__":
    unittest.main()
