"""Funções compartilhadas: dados (Kaggle e TSPLIB via download), instâncias, rotas e cronômetro."""

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
from typing import Callable, Iterable, Iterator, Sequence, TypeVar

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATASET_FILE = DATA_DIR / "tsp_dataset.csv"
# Second CSV of the same Kaggle bundle: 113 instances of 20-149 cities, coordinates only.
EXTRA_DATASET_FILE = DATA_DIR / "tsp_instances_dataset.csv"
DATASET_URL = ("https://www.kaggle.com/api/v1/datasets/download/"
               "ziya07/traveling-salesman-problem-tsplib-dataset")
DATASET_MEMBERS = (DATASET_FILE.name, EXTRA_DATASET_FILE.name)
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
    """Baixa a base do Kaggle se o CSV pedido ainda não existir localmente."""
    if path.is_file():
        return path
    if path.name not in DATASET_MEMBERS:
        raise FileNotFoundError(f"{path} não existe e não faz parte da base do Kaggle")
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = path.with_suffix(".zip.part")
    print(f"Baixando {DATASET_URL} ...", flush=True)
    try:
        with urllib.request.urlopen(DATASET_URL, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response, \
                archive.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        with zipfile.ZipFile(archive) as bundle:
            for member in DATASET_MEMBERS:
                target = path.parent / member
                if target.is_file():
                    continue
                if member not in bundle.namelist():
                    raise RuntimeError(f"{member} não encontrado no arquivo baixado")
                # Only known members go to fixed paths, so archive paths are never trusted.
                partial = target.with_suffix(".csv.part")
                with bundle.open(member) as source, partial.open("wb") as output:
                    shutil.copyfileobj(source, output)
                partial.replace(target)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RuntimeError(
            f"Falha ao baixar a base ({exc}). Baixe manualmente em "
            "https://www.kaggle.com/datasets/ziya07/traveling-salesman-problem-tsplib-dataset "
            f"e salve {', '.join(DATASET_MEMBERS)} em {path.parent}"
        ) from exc
    finally:
        archive.unlink(missing_ok=True)
    return path


def _read_rows(path: Path) -> Iterator[dict[str, str]]:
    csv.field_size_limit(CSV_FIELD_LIMIT)
    with ensure_dataset(path).open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def load_instance_groups(sizes: Iterable[int], per_size: int,
                         path: Path = DATASET_FILE) -> dict[int, list[Instance]]:
    """Para cada tamanho, as `per_size` instâncias de menor instance_id (ordem crescente)."""
    if per_size < 1:
        raise ValueError("per_size deve ser >= 1")
    wanted = set(sizes)
    chosen: dict[int, list[dict[str, str]]] = {size: [] for size in wanted}
    for row in _read_rows(path):
        size = int(row["num_cities"])
        if size in wanted:
            group = chosen[size]
            group.append(row)
            group.sort(key=lambda item: int(item["instance_id"]))
            del group[per_size:]
    missing = sorted(size for size, rows in chosen.items() if not rows)
    if missing:
        raise ValueError(f"A base não tem instâncias com {missing} cidades")
    return {size: [parse_instance(row) for row in rows] for size, rows in chosen.items()}


def load_instances(sizes: Iterable[int], path: Path = DATASET_FILE) -> dict[int, Instance]:
    """Retorna, para cada tamanho pedido, a instância de menor instance_id com esse tamanho."""
    return {size: group[0] for size, group in load_instance_groups(sizes, 1, path).items()}


def iter_instances(path: Path = DATASET_FILE) -> Iterator[Instance]:
    """Percorre todas as instâncias da base, uma por vez (sem manter o CSV em memória)."""
    for row in _read_rows(path):
        yield parse_instance(row)


def load_extra_instances(min_cities: int = 2,
                         path: Path = EXTRA_DATASET_FILE) -> list[Instance]:
    """Instâncias do tsp_instances_dataset.csv com pelo menos `min_cities` cidades.

    A coluna TSP_Instance repete nomes do TSPLIB que não correspondem aos dados
    (por exemplo, "berlin52" com 140 cidades), então a instância é identificada
    pela linha do arquivo. As distâncias são euclidianas, calculadas das coordenadas.
    """
    instances = []
    for line, row in enumerate(_read_rows(path), start=1):
        size = int(row["Num_Cities"])
        if size < min_cities:
            continue
        points = [(float(row[f"City_{i}_X"]), float(row[f"City_{i}_Y"]))
                  for i in range(1, size + 1)]
        instances.append(instance_from_points(line, points, f"K2-{line}"))
    return instances


def instance_from_points(instance_id: int, points: Sequence[tuple[float, float]], label: str,
                         distance: Callable[[tuple[float, float], tuple[float, float]], float]
                         = math.dist) -> Instance:
    """Monta e valida uma instância a partir de coordenadas e de uma função de distância."""
    coordinates = tuple((float(x), float(y)) for x, y in points)
    distances = tuple(tuple(distance(a, b) for b in coordinates) for a in coordinates)
    _validate(instance_id, len(coordinates), coordinates, distances)
    return Instance(instance_id, coordinates, distances, label)


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


# ---------------------------------------------------------------- TSPLIB (ótimo conhecido)
# Os arquivos vêm do espelho github.com/mastqe/tsplib (o servidor original em Heidelberg
# não responde) e ficam em cache em data/tsplib/. As distâncias seguem a definição oficial
# do TSPLIB (inteiros arredondados), pois é nela que os ótimos publicados foram calculados.

TSPLIB_MIRROR_URL = "https://raw.githubusercontent.com/mastqe/tsplib/master/"
TSPLIB_DIR = DATA_DIR / "tsplib"
# Ótimos publicados no TSPLIB (arquivo "solutions" do espelho, igual à página STSP oficial).
TSPLIB_OPTIMA = {
    "att48": 10628, "eil51": 426, "berlin52": 7542, "st70": 675, "eil76": 538,
    "pr76": 108159, "kroA100": 21282, "rd100": 7910, "eil101": 629, "lin105": 14379,
    "ch130": 6110, "ch150": 6528, "kroA150": 26524, "pr152": 73682, "u159": 42080,
    "rat195": 2323, "d198": 15780, "kroA200": 29368, "tsp225": 3916, "gil262": 2378,
    "a280": 2579, "lin318": 42029, "rd400": 15281, "pcb442": 50778,
}
TSPLIB_INSTANCES = tuple(TSPLIB_OPTIMA)


def euc_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    """EUC_2D: distância euclidiana arredondada para o inteiro mais próximo."""
    return float(int(math.dist(a, b) + 0.5))


def att(a: tuple[float, float], b: tuple[float, float]) -> float:
    """ATT: pseudo-euclidiana usada em att48 (definição do TSPLIB)."""
    exact = math.sqrt(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) / 10.0)
    rounded = int(exact + 0.5)
    return float(rounded + 1 if rounded < exact else rounded)


TSPLIB_DISTANCES = {"EUC_2D": euc_2d, "ATT": att}


def ensure_tsplib(name: str) -> Path:
    """Baixa o arquivo .tsp (somente nomes da lista conhecida) se não estiver em cache."""
    if name not in TSPLIB_OPTIMA:
        raise ValueError(f"Instância TSPLIB sem ótimo cadastrado: {name}")
    path = TSPLIB_DIR / f"{name}.tsp"
    if path.is_file():
        return path
    TSPLIB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(TSPLIB_MIRROR_URL + f"{name}.tsp",
                                    timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            content = response.read()
    except OSError as exc:
        raise RuntimeError(f"Falha ao baixar {name}.tsp de {TSPLIB_MIRROR_URL}: {exc}") from exc
    partial = path.with_suffix(".tsp.part")
    partial.write_bytes(content)
    partial.replace(path)
    return path


def parse_tsplib(text: str) -> tuple[dict[str, str], list[tuple[float, float]]]:
    """Lê o cabeçalho (CHAVE : VALOR) e a seção NODE_COORD_SECTION."""
    header: dict[str, str] = {}
    points: list[tuple[float, float]] = []
    in_coordinates = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "EOF":
            continue
        if line == "NODE_COORD_SECTION":
            in_coordinates = True
        elif in_coordinates:
            _, x, y = line.split()[:3]
            points.append((float(x), float(y)))
        elif ":" in line:
            key, value = line.split(":", 1)
            header[key.strip()] = value.strip()
    dimension = int(header.get("DIMENSION", "0"))
    if dimension < 2 or len(points) != dimension:
        raise ValueError(f"DIMENSION={dimension}, mas {len(points)} coordenadas")
    return header, points


def load_tsplib(name: str) -> Instance:
    header, points = parse_tsplib(ensure_tsplib(name).read_text(encoding="utf-8"))
    weight_type = header.get("EDGE_WEIGHT_TYPE", "")
    if weight_type not in TSPLIB_DISTANCES:
        raise ValueError(f"{name}: EDGE_WEIGHT_TYPE {weight_type!r} não suportado")
    return instance_from_points(TSPLIB_INSTANCES.index(name), points, name,
                                TSPLIB_DISTANCES[weight_type])
