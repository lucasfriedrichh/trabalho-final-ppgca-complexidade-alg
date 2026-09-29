"""Funções compartilhadas: base TSP do Kaggle, instâncias, custo de rotas e cronômetro."""

from __future__ import annotations

import csv
import json
import math
import shutil
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeVar

ROOT = Path(__file__).resolve().parent
DATASET_FILE = ROOT / "data" / "tsp_dataset.csv"
DATASET_URL = ("https://www.kaggle.com/api/v1/datasets/download/"
               "ziya07/traveling-salesman-problem-tsplib-dataset")
DATASET_MEMBER = "tsp_dataset.csv"
DOWNLOAD_TIMEOUT_SECONDS = 300
# The distance_matrix column of a 100-city instance is ~570 kB, above csv's 128 kB default.
CSV_FIELD_LIMIT = 16 * 1024 * 1024
MATRIX_TOLERANCE = 1e-6
DATASET_MIN_CITIES = 20  # menor num_cities presente na base

Route = tuple[int, ...]
Matrix = tuple[tuple[float, ...], ...]
T = TypeVar("T")


@dataclass(frozen=True)
class Instance:
    """Uma instância do dataset: cidades 0..n-1, coordenadas e matriz de distâncias."""

    instance_id: int
    coordinates: tuple[tuple[float, float], ...]
    distances: Matrix
    label: str

    @property
    def size(self) -> int:
        return len(self.coordinates)

    def prefix(self, count: int) -> Instance:
        """Sub-instância com as primeiras `count` cidades (mesmas distâncias da base)."""
        if not 2 <= count <= self.size:
            raise ValueError(f"prefix must have 2..{self.size} cities, got {count}")
        return Instance(
            instance_id=self.instance_id,
            coordinates=self.coordinates[:count],
            distances=tuple(row[:count] for row in self.distances[:count]),
            label=f"#{self.instance_id} (primeiras {count})",
        )


@dataclass(frozen=True)
class Solution:
    """Rota fechada (volta à primeira cidade), seu custo e se a busca terminou."""

    route: Route
    cost: float
    status: str = "ok"  # "ok" ou "timeout"


def ensure_dataset(path: Path = DATASET_FILE) -> Path:
    """Baixa a base do Kaggle se o CSV ainda não existir localmente."""
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = path.with_suffix(".zip.part")
    print(f"Baixando {DATASET_URL} ...", flush=True)
    try:
        with urllib.request.urlopen(DATASET_URL, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, \
                archive.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        with zipfile.ZipFile(archive) as bundle:
            if DATASET_MEMBER not in bundle.namelist():
                raise RuntimeError(f"{DATASET_MEMBER} não encontrado no arquivo baixado")
            # Only the known member is copied to a fixed path, so archive paths are never trusted.
            partial = path.with_suffix(".csv.part")
            with bundle.open(DATASET_MEMBER) as source, partial.open("wb") as target:
                shutil.copyfileobj(source, target)
            partial.replace(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError(
            f"Falha ao baixar a base ({exc}). Baixe manualmente em "
            "https://www.kaggle.com/datasets/ziya07/traveling-salesman-problem-tsplib-dataset "
            f"e salve {DATASET_MEMBER} em {path.parent}"
        ) from exc
    finally:
        archive.unlink(missing_ok=True)
    return path


def load_instances(sizes: Iterable[int], path: Path = DATASET_FILE) -> dict[int, Instance]:
    """Retorna, para cada tamanho pedido, a instância de menor instance_id com esse tamanho."""
    wanted = set(sizes)
    chosen: dict[int, dict[str, str]] = {}
    csv.field_size_limit(CSV_FIELD_LIMIT)
    with ensure_dataset(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            size = int(row["num_cities"])
            if size in wanted and (size not in chosen or
                                   int(row["instance_id"]) < int(chosen[size]["instance_id"])):
                chosen[size] = row
    missing = sorted(wanted - chosen.keys())
    if missing:
        raise ValueError(f"A base não tem instâncias com {missing} cidades")
    return {size: parse_instance(row) for size, row in chosen.items()}


def load_cases(sizes: Sequence[int], path: Path = DATASET_FILE) -> list[Instance]:
    """Uma instância por tamanho, na ordem pedida.

    A base começa em 20 cidades; tamanhos menores viram sub-instâncias com as
    primeiras cidades da instância de 20, para a força bruta ter um ótimo exato.
    """
    if any(size < 2 for size in sizes):
        raise ValueError("Cada caso precisa de pelo menos 2 cidades")
    full_sizes = {max(size, DATASET_MIN_CITIES) for size in sizes}
    instances = load_instances(full_sizes, path)
    base = instances[DATASET_MIN_CITIES] if DATASET_MIN_CITIES in instances else None
    return [base.prefix(size) if size < DATASET_MIN_CITIES and base is not None
            else instances[size] for size in sizes]


def parse_instance(row: dict[str, str]) -> Instance:
    """Converte e valida uma linha do CSV (coordenadas e matriz em JSON)."""
    instance_id = int(row["instance_id"])
    size = int(row["num_cities"])
    coordinates = tuple((float(x), float(y)) for x, y in json.loads(row["city_coordinates"]))
    distances = tuple(tuple(float(value) for value in line)
                      for line in json.loads(row["distance_matrix"]))
    _validate(instance_id, size, coordinates, distances)
    return Instance(instance_id, coordinates, distances, f"#{instance_id}")


def _validate(instance_id: int, size: int, coordinates: Sequence[tuple[float, float]],
              distances: Matrix) -> None:
    problem = None
    if size < 2 or len(coordinates) != size:
        problem = f"{len(coordinates)} coordenadas para num_cities={size}"
    elif len(distances) != size or any(len(line) != size for line in distances):
        problem = "matriz de distâncias não é n x n"
    elif not all(math.isfinite(v) for point in coordinates for v in point):
        problem = "coordenada não finita"
    elif any(not math.isfinite(v) or v < 0 for line in distances for v in line):
        problem = "distância negativa ou não finita"
    elif any(abs(distances[i][i]) > MATRIX_TOLERANCE for i in range(size)):
        problem = "diagonal da matriz diferente de zero"
    elif any(abs(distances[i][j] - distances[j][i]) > MATRIX_TOLERANCE
             for i in range(size) for j in range(i)):
        problem = "matriz não simétrica"
    if problem:
        raise ValueError(f"Instância {instance_id} inválida: {problem}")


def route_cost(route: Sequence[int], distances: Matrix) -> float:
    """Comprimento do circuito, incluindo o retorno à cidade inicial."""
    return sum(distances[route[i - 1]][route[i]] for i in range(len(route)))


def is_valid_route(route: Sequence[int], size: int) -> bool:
    """Uma rota válida visita cada cidade 0..size-1 exatamente uma vez."""
    return len(route) == size and sorted(route) == list(range(size))


def timed(function: Callable[[], T]) -> tuple[T, float]:
    """Executa `function` e devolve o resultado e o tempo em segundos."""
    start = time.perf_counter()
    result = function()
    return result, time.perf_counter() - start
