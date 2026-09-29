"""Geração de gráficos, GIFs e tabelas na pasta docs/.

A partir de docs/data/results.csv (gravado por benchmarks.py) são gerados o
resumo docs/README.md com as tabelas de comparação, docs/tables/results.md e
docs/graphs/comparison.png. Os GIFs são desenhados a partir do histórico de
cada abordagem durante a própria execução.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from bruteforce import SKIP_FROM_CITIES, route_count
from utils import Instance, Route

ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
ALGORITHMS = ("Brute force", "Genetic", "Greedy")
NAMES = {"Brute force": "Força bruta", "Genetic": "Genético", "Greedy": "Guloso"}
COLORS = {"Brute force": "tab:red", "Genetic": "tab:blue", "Greedy": "tab:green"}
NUMERIC = ("execution", "cities", "distance", "seconds")
GIF_FRAMES = 18
GIF_FRAME_MILLISECONDS = 220
GIF_WIDTH_PIXELS = 260


# ---------------------------------------------------------------- CSV e formatação

def write_csv(path: Path, rows: list[dict], fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in NUMERIC:
            row[key] = float(row[key]) if row[key] else None
    return rows


def _number(value: float, pattern: str) -> str:
    return format(value, pattern).replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_distance(value: float | None) -> str:
    return "—" if value is None else _number(value, ",.2f")


def fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 1e-3:
        return f"{_number(seconds * 1e6, '.0f')} µs"
    if seconds < 1:
        return f"{_number(seconds * 1e3, '.2f')} ms"
    return f"{_number(seconds, '.2f')} s"


def fmt_percent(value: float | None) -> str:
    return "—" if value is None else f"{_number(value, '+.1f')}%"


def fmt_ratio(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{_number(value, ',.0f' if value >= 100 else '.1f')}×"


def md_table(headers: list[str], rows: list[list[str]], align: str) -> list[str]:
    marks = {"l": ":---", "r": "---:", "c": ":---:"}
    return (["| " + " | ".join(headers) + " |",
             "| " + " | ".join(marks[a] for a in align) + " |"]
            + ["| " + " | ".join(row) + " |" for row in rows])


def _difference(value: float | None, reference: float | None) -> float | None:
    """Diferença percentual de value em relação a reference (negativo = menor)."""
    return None if value is None or not reference else 100 * (value / reference - 1)


def _ratio(value: float | None, reference: float | None) -> float | None:
    return None if value is None or not reference else value / reference


# ---------------------------------------------------------------- comparação

def executions(rows: list[dict]) -> list[dict]:
    """Agrupa as linhas do CSV por execução: {"cities", "instance", algoritmo: linha}."""
    grouped: dict[int, dict] = {}
    for row in rows:
        entry = grouped.setdefault(int(row["execution"]), {
            "execution": int(row["execution"]), "cities": int(row["cities"]),
            "instance": row["instance"]})
        entry[row["algorithm"]] = row
    for entry in grouped.values():
        brute = entry["Brute force"]
        entry["optimum"] = brute["distance"] if brute["status"] == "ok" else None
    return [grouped[key] for key in sorted(grouped)]


def _brute_distance(entry: dict) -> str:
    brute = entry["Brute force"]
    if brute["distance"] is None:
        return "não executada ¹"
    suffix = "" if brute["status"] == "ok" else " (timeout)"
    return fmt_distance(brute["distance"]) + suffix


def _best(entry: dict, field: str) -> str:
    values = {name: entry[name][field] for name in ALGORITHMS if entry[name][field] is not None}
    best = min(values.values())
    winners = [NAMES[name] for name, value in values.items() if abs(value - best) < 1e-9]
    return " = ".join(winners)


def distance_table(runs: list[dict]) -> list[str]:
    table = [[str(e["execution"]), str(e["cities"]), e["instance"], _brute_distance(e),
              fmt_distance(e["Genetic"]["distance"]), fmt_distance(e["Greedy"]["distance"]),
              _best(e, "distance"),
              fmt_percent(_difference(e["Genetic"]["distance"], e["Greedy"]["distance"])),
              fmt_percent(_difference(e["Genetic"]["distance"], e["optimum"])),
              fmt_percent(_difference(e["Greedy"]["distance"], e["optimum"]))] for e in runs]
    return md_table(["Execução", "Cidades", "Instância", "Força bruta", "Genético", "Guloso",
                     "Menor distância", "Genético vs guloso", "Genético vs ótimo",
                     "Guloso vs ótimo"], table, "rrlrrrlrrr")


def time_table(runs: list[dict]) -> list[str]:
    table = [[str(e["execution"]), str(e["cities"]),
              fmt_time(e["Brute force"]["seconds"]) if e["Brute force"]["seconds"] is not None
              else "não executada ¹",
              fmt_time(e["Genetic"]["seconds"]), fmt_time(e["Greedy"]["seconds"]),
              _best(e, "seconds"),
              fmt_ratio(_ratio(e["Genetic"]["seconds"], e["Greedy"]["seconds"])),
              fmt_ratio(_ratio(e["Brute force"]["seconds"], e["Greedy"]["seconds"]))]
             for e in runs]
    return md_table(["Execução", "Cidades", "Força bruta", "Genético", "Guloso", "Mais rápido",
                     "Genético ÷ guloso", "Força bruta ÷ guloso"], table, "rrrrrlrr")


def detail_table(rows: list[dict]) -> list[str]:
    table = [[str(int(r["execution"])), str(int(r["cities"])), r["instance"],
              NAMES[r["algorithm"]], fmt_distance(r["distance"]), fmt_time(r["seconds"]),
              r["status"]] for r in rows]
    return md_table(["Execução", "Cidades", "Instância", "Abordagem", "Distância total",
                     "Tempo", "Status"], table, "rrllrrl")


# ---------------------------------------------------------------- gráfico

def render_chart(runs: list[dict], path: Path) -> None:
    labels = [f"{e['cities']} cidades" for e in runs]
    positions = np.arange(len(runs))
    width = 0.27
    figure, (distance, runtime, difference) = plt.subplots(1, 3, figsize=(17, 5))
    for index, name in enumerate(ALGORITHMS):
        offset = (index - 1) * width
        for axis, field in ((distance, "distance"), (runtime, "seconds")):
            values = [e[name][field] for e in runs]
            axis.bar(positions + offset, [v or 0 for v in values], width,
                     color=COLORS[name], label=NAMES[name])
            for position, value in zip(positions, values):
                if value is None:
                    # x in data units, y as a fraction of the axis: works on the log scale too.
                    axis.text(position + offset, 0.02, "não executada", ha="center",
                              va="bottom", rotation=90, fontsize=7, color=COLORS[name],
                              transform=axis.get_xaxis_transform())
    differences = []
    for index, (name, label) in enumerate((("Genetic", "Genético"),
                                           ("Brute force", "Força bruta (ótimo)"))):
        values = [_difference(e[name]["distance"], e["Greedy"]["distance"]) for e in runs]
        differences += [v for v in values if v is not None]
        difference.bar(positions + (index - 0.5) * width, [v or 0 for v in values], width,
                       color=COLORS[name], label=label)
        for position, value in zip(positions, values):
            if value is not None:
                text = "0%" if abs(value) < 0.05 else fmt_percent(value)
                difference.text(position + (index - 0.5) * width, value, text, ha="center",
                                va="top" if value < -0.05 else "bottom", fontsize=7)
    # Headroom above zero keeps the "0%" labels clear of the title.
    difference.set_ylim(min(differences + [0]) * 1.15 - 1, max(differences + [0]) * 1.15 + 2)
    difference.axhline(0, color=COLORS["Greedy"], linewidth=1.5, label="Guloso (referência)")
    distance.set(title="Distância total (menor é melhor)", ylabel="Distância")
    runtime.set(title="Tempo de execução (escala log)", ylabel="Segundos", yscale="log")
    difference.set(title="Diferença de distância em relação ao guloso",
                   ylabel="% (negativo = rota menor)")
    for axis in (distance, runtime, difference):
        axis.set_xticks(positions, labels)
        axis.grid(alpha=0.3, axis="y")
        axis.legend(fontsize=8)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


# ---------------------------------------------------------------- GIFs

def _frame(figure) -> Image.Image:
    """Copia o desenho do Matplotlib antes de reutilizar a figura."""
    figure.canvas.draw()
    width, height = figure.canvas.get_width_height()
    return Image.frombytes("RGBA", (width, height),
                           bytes(figure.canvas.buffer_rgba())).convert("RGB")


def _draw_cities(axis, instance: Instance, title: str, subtitle: str) -> None:
    axis.clear()
    xs = [x for x, _ in instance.coordinates]
    ys = [y for _, y in instance.coordinates]
    axis.scatter(xs, ys, s=22, color="#d35400", zorder=2)
    axis.set_title(title, fontsize=12)
    axis.set_xlabel(subtitle, fontsize=9)
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.2)
    xpad = max(max(xs) - min(xs), 1) * 0.08
    ypad = max(max(ys) - min(ys), 1) * 0.08
    axis.set_xlim(min(xs) - xpad, max(xs) + xpad)
    axis.set_ylim(min(ys) - ypad, max(ys) + ypad)


def _draw_edges(axis, instance: Instance, edges) -> None:
    for a, b in edges:
        (x1, y1), (x2, y2) = instance.coordinates[a], instance.coordinates[b]
        axis.plot([x1, x2], [y1, y2], color="#1967a3", linewidth=1.8, zorder=1)


def _route_edges(route: Route) -> list[tuple[int, int]]:
    return [(route[i - 1], route[i]) for i in range(len(route))]


def _sampled(items: list) -> list:
    """Até GIF_FRAMES itens espaçados, sempre com o primeiro e o último."""
    if len(items) <= GIF_FRAMES:
        return items
    indexes = sorted({round(i * (len(items) - 1) / (GIF_FRAMES - 1)) for i in range(GIF_FRAMES)})
    return [items[i] for i in indexes]


def gif_path(output: Path, algorithm: str, cities: int) -> Path:
    prefix = {"Brute force": "brute_force", "Genetic": "genetic", "Greedy": "greedy"}[algorithm]
    return output / "gifs" / f"{prefix}_{cities}.gif"


def _save_gif(frames: list[Image.Image], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=GIF_FRAME_MILLISECONDS, loop=0, optimize=True)


def render_greedy_gif(instance: Instance, edges: list[tuple[int, int]], cost: float,
                      output: Path) -> None:
    """Arestas aceitas pelo guloso, da menor para a maior."""
    figure, axis = plt.subplots(figsize=(7, 5), dpi=90)
    try:
        frames = []
        for step in _sampled(list(range(1, len(edges) + 1))):
            subtitle = (f"{step}/{instance.size} arestas · distância: {cost:.1f}"
                        if step == len(edges) else
                        f"{step}/{instance.size} arestas, da menor para a maior")
            _draw_cities(axis, instance, f"Guloso · {instance.label}", subtitle)
            _draw_edges(axis, instance, edges[:step])
            frames.append(_frame(figure))
        _save_gif(frames, gif_path(output, "Greedy", instance.size))
    finally:
        plt.close(figure)


def render_genetic_gif(instance: Instance, history: list[tuple[int, Route, float]],
                       generations: int, output: Path) -> None:
    """Melhor rota por geração e curva da melhor distância."""
    costs = [cost for _, _, cost in history]
    figure, (route_axis, cost_axis) = plt.subplots(1, 2, figsize=(10, 4.8), dpi=90)
    try:
        frames = []
        for generation, route, cost in _sampled(history):
            _draw_cities(route_axis, instance, f"Genético · {instance.label}",
                         f"Geração {generation}/{generations} · distância: {cost:.1f}")
            _draw_edges(route_axis, instance, _route_edges(route))
            cost_axis.clear()
            cost_axis.plot(range(1, generation + 1), costs[:generation], color="#16783c")
            cost_axis.set_xlim(1, max(generations, 2))
            margin = max((max(costs) - min(costs)) * 0.12, 1)
            cost_axis.set_ylim(min(costs) - margin, max(costs) + margin)
            cost_axis.set(title="Melhor distância por geração", xlabel="Geração",
                          ylabel="Distância")
            cost_axis.grid(alpha=0.2)
            figure.tight_layout()
            frames.append(_frame(figure))
        _save_gif(frames, gif_path(output, "Genetic", instance.size))
    finally:
        plt.close(figure)


def render_brute_force_gif(instance: Instance, improvements: list[tuple[int, Route, float]],
                           output: Path) -> None:
    """Cada melhoria encontrada durante a enumeração, terminando no ótimo."""
    total = route_count(instance.size)
    figure, axis = plt.subplots(figsize=(7, 5), dpi=90)
    try:
        frames = []
        for count, route, cost in _sampled(improvements):
            _draw_cities(axis, instance, f"Força bruta · {instance.label}",
                         f"{count}/{total} rotas avaliadas · melhor distância: {cost:.1f}")
            _draw_edges(axis, instance, _route_edges(route))
            frames.append(_frame(figure))
        _, route, cost = improvements[-1]
        _draw_cities(axis, instance, f"Força bruta · {instance.label}",
                     f"{total}/{total} rotas · ótimo: {cost:.1f}")
        _draw_edges(axis, instance, _route_edges(route))
        frames.append(_frame(figure))
        _save_gif(frames, gif_path(output, "Brute force", instance.size))
    finally:
        plt.close(figure)


def gif_table(runs: list[dict], output: Path) -> list[str]:
    table = []
    for e in runs:
        cells = []
        for name in ALGORITHMS:
            path = gif_path(output, name, e["cities"])
            cells.append(f'<img src="gifs/{path.name}" width="{GIF_WIDTH_PIXELS}">'
                         if path.is_file() else "—")
        table.append([f"{e['execution']} ({e['cities']} cidades)", *cells])
    return md_table(["Execução", "Força bruta", "Genético", "Guloso"], table, "lccc")


# ---------------------------------------------------------------- docs/README.md

def build_docs(output: Path = DOCS_DIR, brute_timeout: float = 600) -> Path:
    """Gera docs/README.md (comparação), docs/tables/results.md e o gráfico a partir do CSV."""
    rows = load_csv(output / "data" / "results.csv")
    runs = executions(rows)
    render_chart(runs, output / "graphs" / "comparison.png")
    tables = output / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "results.md").write_text(
        "\n".join(["# Resultados por abordagem", "", *detail_table(rows), ""]), encoding="utf-8")

    sizes = ", ".join(str(e["cities"]) for e in runs)
    lines = [
        "# Resultados", "",
        f"{len(runs)} execuções com {sizes} cidades. Em cada execução, força bruta, genético e "
        "guloso resolvem **a mesma instância** da base do Kaggle (`#id` = `instance_id`; "
        "`primeiras k` = só as k primeiras cidades da instância). Gerado por "
        "`python benchmarks.py`.", "",
        "## Distância total", "",
        *distance_table(runs), "",
        "Distância do circuito completo, com retorno à cidade inicial. **Genético vs guloso**: "
        "diferença da distância do genético em relação à do guloso (negativo = rota menor). "
        "**vs ótimo**: diferença em relação à rota ótima exata da força bruta, disponível "
        "somente quando ela é executada.", "",
        "## Tempo de execução", "",
        *time_table(runs), "",
        "**Genético ÷ guloso** e **Força bruta ÷ guloso**: quantas vezes a abordagem foi mais "
        "lenta que o guloso.", "",
        f"¹ A força bruta avalia `(n-1)!/2` rotas. A partir de {SKIP_FROM_CITIES} cidades ela "
        f"não é executada e é registrada como `timeout`; até {SKIP_FROM_CITIES - 1} cidades, "
        f"roda com prazo de {brute_timeout:g} s.", "",
        "## Gráfico", "",
        "![Comparação](graphs/comparison.png)", "",
        "## GIFs", "",
        *gif_table(runs, output), "",
        "## Arquivos", "",
        "- Dados brutos: [data/results.csv](data/results.csv)",
        "- Tabela por abordagem: [tables/results.md](tables/results.md)",
        "- Gráfico: [graphs/comparison.png](graphs/comparison.png)", "",
    ]
    readme = output / "README.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme
