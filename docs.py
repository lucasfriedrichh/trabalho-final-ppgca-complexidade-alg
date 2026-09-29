"""Geração de gráficos, GIFs e tabelas na pasta docs/.

Os resultados brutos ficam em docs/data/*.csv; a partir deles são gerados
docs/tables/*.md, docs/graphs/*.png e o resumo docs/README.md. Os GIFs são
desenhados a partir do histórico de cada algoritmo, recebido de benchmarks.py.
"""

from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
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
COLORS = {"Genetic": "tab:blue", "Greedy": "tab:green", "Brute force": "tab:red"}
NAMES = {"Genetic": "Genético", "Greedy": "Guloso", "Brute force": "Força bruta"}
ALGORITHMS = ("Genetic", "Greedy", "Brute force")
NUMERIC = ("cities", "seed", "distance", "seconds", "reference", "gap_reference", "vs_greedy",
           "generation", "best")
# Beardwood-Halton-Hammersley: optimal tour ~ 0.7124 * sqrt(n * A) for uniform points, n -> inf.
BHH_CONSTANT = 0.7124
KAGGLE_AREA = 100 * 100  # coordenadas da base entre 0 e 100
PROJECTION_SIZES = (13, 14, 15, 16, 18, 20, 25, 30, 50, 100)
SECONDS_PER_YEAR = 365.25 * 86400
UNIVERSE_AGE_YEARS = 13.8e9
GIF_FRAME_MILLISECONDS = 220


# ---------------------------------------------------------------- CSV e formatação

def write_csv(path: Path, rows: list[dict], fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in NUMERIC:
            if key in row:
                row[key] = float(row[key]) if row[key] not in ("", None) else None
    return rows


def by_algorithm(rows: list[dict], algorithm: str) -> list[dict]:
    return [row for row in rows if row["algorithm"] == algorithm and row["distance"] is not None]


def fmt(value, pattern: str = ".2f") -> str:
    return "—" if value is None else format(value, pattern).replace(".", ",")


def thousands(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def scientific(value: float) -> str:
    """1,6 × 10^142 em vez de 1.6e+142."""
    exponent = int(math.floor(math.log10(value)))
    return f"{fmt(value / 10 ** exponent, '.1f')} × 10^{exponent}"


def duration(seconds: float) -> str:
    """Tempo legível: ms, s, min, h, dias ou anos (notação científica acima de 1 milhão)."""
    if seconds < 1:
        return f"{fmt(seconds * 1000, '.3g')} ms"
    if seconds < 60:
        return f"{fmt(seconds, '.2f')} s"
    if seconds < 3600:
        return f"{fmt(seconds / 60, '.1f')} min"
    if seconds < 86400:
        return f"{fmt(seconds / 3600, '.1f')} h"
    years = seconds / SECONDS_PER_YEAR
    if years < 1:
        return f"{fmt(seconds / 86400, '.1f')} dias"
    return f"{thousands(years)} anos" if years < 1e6 else f"{scientific(years)} anos"


def md_table(headers: list[str], rows: list[list[str]], align: str) -> list[str]:
    marks = {"l": ":---", "r": "---:", "c": ":---:"}
    return (["| " + " | ".join(headers) + " |",
             "| " + " | ".join(marks[a] for a in align) + " |"]
            + ["| " + " | ".join(row) + " |" for row in rows])


def write_table(path: Path, title: str, notes: list[str], headers: list[str],
                rows: list[list[str]], align: str, extra: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", *notes, *([""] if notes else [])]
    lines += md_table(headers, rows, align) + (extra or [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_figure(figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def slope(xs, ys) -> float:
    """Expoente k de t ~ n^k (regressão em escala log-log)."""
    return float(np.polyfit(np.log(xs), np.log(ys), 1)[0])


def _find(rows, algorithm, key, value, field):
    for row in rows:
        if row["algorithm"] == algorithm and row[key] == value:
            return row[field]
    return None


def _size(rows, label) -> int:
    return int(next(r["cities"] for r in rows if r["instance"] == label))


def _note_optimum_hits(axis, gaps: list[float]) -> None:
    """Barras de altura zero não aparecem: explica no gráfico quando o AG acerta o ótimo."""
    hits = sum(gap < 1e-6 for gap in gaps)
    if hits:
        axis.text(0.5, 0.95, f"Genético atingiu o ótimo em {hits}/{len(gaps)} casos "
                  "(barra de altura 0)", transform=axis.transAxes, ha="center", va="top",
                  color=COLORS["Genetic"], fontsize=9,
                  bbox={"facecolor": "white", "edgecolor": COLORS["Genetic"], "alpha": 0.9})


# ---------------------------------------------------------------- benchmark principal

def render_benchmark(output: Path, brute_timeout: float) -> list[str]:
    rows = load_csv(output / "data" / "benchmark.csv")
    if not rows:
        return []
    table = [[str(int(r["cities"])), r["instance"], r["algorithm"], fmt(r["distance"]),
              fmt(r["seconds"], ".4f"), r["status"], fmt(r["vs_greedy"], "+.1f")] for r in rows]
    notes = ["Instância `#id` é o `instance_id` da base do Kaggle; `(primeiras k)` indica a "
             "sub-instância com as k primeiras cidades. `vs guloso`: diferença de distância em "
             "relação ao guloso (negativo = rota menor). `ok`: execução concluída (na força "
             f"bruta, ótimo exato). `timeout`: a partir de {SKIP_FROM_CITIES} cidades a força "
             "bruta não é executada, pois as `(n-1)!/2` rotas não terminariam no prazo; entre 11 e "
             f"{SKIP_FROM_CITIES - 1} cidades, é a melhor rota encontrada em até "
             f"{brute_timeout:g} s."]
    write_table(output / "tables" / "benchmark.md", "Resultados do benchmark", notes,
                ["Cidades", "Instância", "Algoritmo", "Distância percorrida", "Tempo (s)",
                 "Status", "vs guloso (%)"], table, "rllrrlr")

    sizes = sorted({row["cities"] for row in rows})
    # Evenly spaced positions keep the 8/9/10 prefixes readable next to 20..100.
    position = {size: index for index, size in enumerate(sizes)}
    figure, (quality, runtime) = plt.subplots(1, 2, figsize=(12, 5))
    for algorithm in ALGORITHMS:
        data = sorted(by_algorithm(rows, algorithm), key=lambda row: row["cities"])
        if not data:
            continue
        brute = algorithm == "Brute force"
        style = {"color": COLORS[algorithm], "marker": "*" if brute else "o",
                 "linestyle": "none" if brute else "-", "markersize": 12 if brute else 6,
                 "label": "Força bruta (exata)" if brute else NAMES[algorithm]}
        xs = [position[row["cities"]] for row in data]
        quality.plot(xs, [row["distance"] for row in data], **style)
        runtime.plot(xs, [row["seconds"] for row in data], **style)
    quality.set(title="Distância da rota (menor é melhor)", xlabel="Cidades", ylabel="Distância")
    runtime.set(title="Tempo de execução (escala log)", xlabel="Cidades", ylabel="Segundos",
                yscale="log")
    for axis in (quality, runtime):
        axis.set_xticks(range(len(sizes)), labels=[str(int(size)) for size in sizes])
        axis.grid(alpha=0.3)
        axis.legend()
    figure.suptitle("Base Kaggle | 8-10 cidades: primeiras cidades da instância de 20 | "
                    f"força bruta não executada a partir de {SKIP_FROM_CITIES} cidades")
    save_figure(figure, output / "graphs" / "comparison.png")
    genetic = [r["vs_greedy"] for r in by_algorithm(rows, "Genetic") if r["cities"] >= 20]
    return [f"AG vs guloso nas instâncias completas: média "
            f"{fmt(statistics.mean(genetic), '+.1f')}%."] if genetic else []


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


def _sampled(items: list, max_frames: int) -> list:
    """Até max_frames itens espaçados, sempre com o primeiro e o último."""
    if len(items) <= max_frames:
        return items
    indexes = sorted({round(i * (len(items) - 1) / (max_frames - 1)) for i in range(max_frames)})
    return [items[i] for i in indexes]


def _save_gif(frames: list[Image.Image], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=GIF_FRAME_MILLISECONDS, loop=0, optimize=True)
    shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    print(f"Criado: {shown} ({len(frames)} quadros)", flush=True)


def render_greedy_gif(instance: Instance, edges: list[tuple[int, int]], cost: float,
                      output: Path, max_frames: int) -> None:
    """Arestas aceitas pelo guloso, da menor para a maior."""
    figure, axis = plt.subplots(figsize=(7, 5), dpi=90)
    try:
        frames = []
        for step in _sampled(list(range(1, len(edges) + 1)), max_frames):
            subtitle = (f"{step}/{instance.size} arestas · distância: {cost:.1f}"
                        if step == len(edges) else
                        f"{step}/{instance.size} arestas, da menor para a maior")
            _draw_cities(axis, instance, f"Guloso de arestas · {instance.label}", subtitle)
            _draw_edges(axis, instance, edges[:step])
            frames.append(_frame(figure))
        _save_gif(frames, output / "gifs" / f"greedy_{instance.size}.gif")
    finally:
        plt.close(figure)


def render_genetic_gif(instance: Instance, history: list[tuple[int, Route, float]],
                       generations: int, output: Path, max_frames: int) -> None:
    """Melhor rota por geração e curva da melhor distância."""
    costs = [cost for _, _, cost in history]
    figure, (route_axis, cost_axis) = plt.subplots(1, 2, figsize=(10, 4.8), dpi=90)
    try:
        frames = []
        for generation, route, cost in _sampled(history, max_frames):
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
        _save_gif(frames, output / "gifs" / f"genetic_{instance.size}.gif")
    finally:
        plt.close(figure)


def render_brute_force_gif(instance: Instance, improvements: list[tuple[int, Route, float]],
                           output: Path, max_frames: int) -> None:
    """Cada melhoria encontrada durante a enumeração, terminando no ótimo."""
    total = route_count(instance.size)
    figure, axis = plt.subplots(figsize=(7, 5), dpi=90)
    try:
        frames = []
        for count, route, cost in _sampled(improvements, max_frames):
            _draw_cities(axis, instance, f"Força bruta · {instance.label}",
                         f"{count}/{total} rotas avaliadas · melhor distância: {cost:.1f}")
            _draw_edges(axis, instance, _route_edges(route))
            frames.append(_frame(figure))
        _, route, cost = improvements[-1]
        _draw_cities(axis, instance, f"Força bruta · {instance.label}",
                     f"{total}/{total} rotas · ótimo: {cost:.1f}")
        _draw_edges(axis, instance, _route_edges(route))
        frames.append(_frame(figure))
        _save_gif(frames, output / "gifs" / f"brute_force_{instance.size}.gif")
    finally:
        plt.close(figure)


# ---------------------------------------------------------------- experimentos E1-E8

def report_e1(rows, output) -> list[str]:
    brute = sorted(by_algorithm(rows, "Brute force"), key=lambda r: r["cities"])
    largest = brute[-1]
    rate = route_count(int(largest["cities"])) / largest["seconds"]
    figure, (times, gaps) = plt.subplots(1, 2, figsize=(13, 5))
    for algorithm in ("Brute force", "Genetic", "Greedy"):
        data = sorted(by_algorithm(rows, algorithm), key=lambda r: r["cities"])
        times.plot([r["cities"] for r in data], [r["seconds"] for r in data], marker="o",
                   color=COLORS[algorithm], label=f"{NAMES[algorithm]} (medido)")
    projected = list(range(int(largest["cities"]), 21))
    times.plot(projected, [route_count(n) / rate for n in projected], "--", color="tab:red",
               label="Força bruta (projeção)")
    for limit, label in ((60, "1 min"), (3600, "1 h"), (SECONDS_PER_YEAR, "1 ano")):
        times.axhline(limit, color="gray", linewidth=0.8, linestyle=":")
        times.text(4.1, limit * 1.3, label, color="gray", fontsize=8)
    times.set(yscale="log", xlabel="Cidades", ylabel="Segundos (escala log)",
              title="Tempo de execução: O(n!) contra polinomial")
    sizes = [int(r["cities"]) for r in brute]
    for offset, algorithm in ((-0.19, "Genetic"), (0.19, "Greedy")):
        data = {int(r["cities"]): r["gap_reference"] for r in by_algorithm(rows, algorithm)}
        gaps.bar([n + offset for n in sizes], [data.get(n, 0) for n in sizes], 0.38,
                 color=COLORS[algorithm], label=NAMES[algorithm])
    _note_optimum_hits(gaps, [r["gap_reference"] for r in by_algorithm(rows, "Genetic")])
    gaps.set(xlabel="Cidades", ylabel="% acima do ótimo", xticks=sizes,
             title="Distância até o ótimo exato (força bruta)")
    for axis in (times, gaps):
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    save_figure(figure, output / "graphs" / "E1_brute_force_growth.png")

    measured = [[str(int(r["cities"])), thousands(route_count(int(r["cities"]))),
                 duration(r["seconds"]), thousands(route_count(int(r["cities"])) / r["seconds"]),
                 fmt(_find(rows, "Genetic", "cities", r["cities"], "gap_reference"), "+.2f"),
                 fmt(_find(rows, "Greedy", "cities", r["cities"], "gap_reference"), "+.2f")]
                for r in brute]
    projection = [[str(n), scientific(route_count(n)), duration(route_count(n) / rate)]
                  for n in PROJECTION_SIZES]
    extra = ["", f"## Projeção (mesma máquina, {thousands(rate)} rotas/s)", "",
             f"Idade do universo: {scientific(UNIVERSE_AGE_YEARS)} anos.", ""]
    extra += md_table(["Cidades", "Rotas", "Tempo estimado"], projection, "rrr")
    write_table(output / "tables" / "E1.md", "E1 — Crescimento da força bruta",
                ["Sub-instâncias com as primeiras n cidades da instância #20 do Kaggle."],
                ["Cidades", "Rotas (n-1)!/2", "Tempo força bruta", "Rotas/s",
                 "AG vs ótimo (%)", "Guloso vs ótimo (%)"], measured, "rrrrrr", extra)
    years_25 = route_count(25) / rate / SECONDS_PER_YEAR
    return [f"Força bruta com {int(largest['cities'])} cidades: {duration(largest['seconds'])} "
            f"({thousands(rate)} rotas/s avaliadas).",
            f"Projeção na mesma máquina: 15 cidades → {duration(route_count(15) / rate)}; "
            f"20 → {duration(route_count(20) / rate)}; 25 → {duration(route_count(25) / rate)} "
            f"({fmt(years_25 / UNIVERSE_AGE_YEARS * 100, '.0f')}% da idade do universo); "
            f"100 → {duration(route_count(100) / rate)}."]


def report_e2(rows, output) -> list[str]:
    def gap(algorithm, label):
        return _find(rows, algorithm, "instance", label, "gap_reference")

    instances = sorted({r["instance"] for r in rows}, key=lambda label: gap("Greedy", label))
    figure, axis = plt.subplots(figsize=(13, 4.8))
    positions = np.arange(len(instances))
    for offset, algorithm in ((-0.2, "Genetic"), (0.2, "Greedy")):
        axis.bar(positions + offset, [gap(algorithm, i) for i in instances], 0.4,
                 color=COLORS[algorithm], label=NAMES[algorithm])
    _note_optimum_hits(axis, [gap("Genetic", i) for i in instances])
    axis.set_xticks(positions, [label.split(" ")[0] for label in instances], rotation=45)
    axis.set(ylabel="% acima do ótimo", xlabel="Instância (10 primeiras cidades)",
             title="Gap até o ótimo exato em 20 sub-instâncias de 10 cidades")
    axis.grid(alpha=0.3, axis="y")
    axis.legend()
    save_figure(figure, output / "graphs" / "E2_exact_gap.png")
    table = [[label, fmt(_find(rows, "Brute force", "instance", label, "distance")),
              fmt(_find(rows, "Genetic", "instance", label, "distance")),
              fmt(gap("Genetic", label), "+.2f"),
              fmt(_find(rows, "Greedy", "instance", label, "distance")),
              fmt(gap("Greedy", label), "+.2f")] for label in instances]
    write_table(output / "tables" / "E2.md", "E2 — Gap até o ótimo exato (10 cidades)", [],
                ["Instância", "Ótimo", "AG", "AG gap (%)", "Guloso", "Guloso gap (%)"],
                table, "lrrrrr")
    summary = []
    for algorithm in ("Genetic", "Greedy"):
        gaps = [gap(algorithm, i) for i in instances]
        summary.append(f"{NAMES[algorithm]}: ótimo em {sum(g < 1e-6 for g in gaps)}/{len(gaps)} "
                       f"instâncias; gap médio {fmt(statistics.mean(gaps), '.2f')}%, máximo "
                       f"{fmt(max(gaps), '.2f')}%.")
    return summary


def report_e3(rows, output) -> list[str]:
    genetic = sorted(by_algorithm(rows, "Genetic"), key=lambda r: r["cities"])
    greedy = sorted(by_algorithm(rows, "Greedy"), key=lambda r: r["cities"])
    sizes = [r["cities"] for r in genetic]
    figure, (length, gain, times) = plt.subplots(1, 3, figsize=(16, 4.8))
    for algorithm, data in (("Genetic", genetic), ("Greedy", greedy)):
        length.plot(sizes, [r["distance"] / math.sqrt(r["cities"] * KAGGLE_AREA) for r in data],
                    marker=".", color=COLORS[algorithm], label=NAMES[algorithm])
    length.axhline(BHH_CONSTANT, color="gray", linestyle="--",
                   label="Ótimo assintótico (BHH, n→∞)")
    length.set(xlabel="Cidades", ylabel="Distância / √(n·área)",
               title="Comprimento normalizado da rota")
    gain.bar(sizes, [r["vs_greedy"] for r in genetic], color=COLORS["Genetic"])
    gain.axhline(statistics.mean(r["vs_greedy"] for r in genetic), color="black",
                 linestyle="--", label="média")
    gain.set(xlabel="Cidades", ylabel="AG vs guloso (%)",
             title="AG em relação ao guloso (negativo = melhor)")
    slopes = {}
    for algorithm, data in (("Genetic", genetic), ("Greedy", greedy)):
        slopes[algorithm] = slope(sizes, [r["seconds"] for r in data])
        times.plot(sizes, [r["seconds"] for r in data], marker=".", color=COLORS[algorithm],
                   label=f"{NAMES[algorithm]} (t ∝ n^{slopes[algorithm]:.2f})")
    times.set(xscale="log", yscale="log", xlabel="Cidades (log)", ylabel="Segundos (log)",
              title="Tempo de execução (log-log)")
    for axis in (length, gain, times):
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    save_figure(figure, output / "graphs" / "E3_all_sizes.png")
    table = [[str(int(a["cities"])), a["instance"], fmt(b["distance"]), fmt(a["distance"]),
              fmt(a["vs_greedy"], "+.1f"), fmt(b["seconds"], ".4f"), fmt(a["seconds"], ".2f")]
             for a, b in zip(genetic, greedy)]
    write_table(output / "tables" / "E3.md", "E3 — Todos os tamanhos da base (20 a 100 cidades)",
                [], ["Cidades", "Instância", "Guloso", "AG", "AG vs guloso (%)", "Guloso (s)",
                     "AG (s)"], table, "rlrrrrr")
    values = [r["vs_greedy"] for r in genetic]
    return [f"AG melhor que o guloso em {sum(v < 0 for v in values)}/{len(values)} tamanhos; "
            f"diferença média {fmt(statistics.mean(values), '+.1f')}% "
            f"(de {fmt(min(values), '+.1f')}% a {fmt(max(values), '+.1f')}%).",
            f"Crescimento empírico do tempo nesta faixa: guloso ∝ n^{fmt(slopes['Greedy'], '.2f')}"
            f", AG ∝ n^{fmt(slopes['Genetic'], '.2f')} (gerações e população fixas)."]


def report_e4(rows, output) -> list[str]:
    groups = defaultdict(list)
    for row in by_algorithm(rows, "Genetic"):
        groups[int(row["cities"])].append(row["vs_greedy"])
    sizes = sorted(groups)
    figure, axis = plt.subplots(figsize=(10, 4.8))
    axis.boxplot([groups[n] for n in sizes], positions=sizes, widths=5)
    axis.plot(sizes, [statistics.mean(groups[n]) for n in sizes], "o--",
              color=COLORS["Genetic"], label="média")
    axis.axhline(0, color=COLORS["Greedy"], label="Guloso (referência)")
    axis.set(xlabel="Cidades", ylabel="AG vs guloso (%)", xticks=sizes,
             title=f"Variação entre instâncias ({len(groups[sizes[0]])} por tamanho)")
    axis.grid(alpha=0.3)
    axis.legend()
    save_figure(figure, output / "graphs" / "E4_instance_variability.png")
    table = [[str(n), str(len(groups[n])), fmt(statistics.mean(groups[n]), "+.1f"),
              fmt(statistics.stdev(groups[n]), ".1f"), fmt(min(groups[n]), "+.1f"),
              fmt(max(groups[n]), "+.1f")] for n in sizes]
    write_table(output / "tables" / "E4.md", "E4 — Variação entre instâncias",
                ["Diferença do AG em relação ao guloso (%), negativo = AG melhor."],
                ["Cidades", "Instâncias", "Média", "Desvio", "Melhor", "Pior"], table, "rrrrrr")
    values = [v for n in sizes for v in groups[n]]
    return [f"{len(values)} instâncias: AG melhor que o guloso em "
            f"{sum(v < 0 for v in values)}; média {fmt(statistics.mean(values), '+.1f')}% "
            f"± {fmt(statistics.stdev(values), '.1f')} (desvio)."]


def report_e5(rows, output) -> list[str]:
    greedy = by_algorithm(rows, "Greedy")
    normalized, times = defaultdict(list), defaultdict(list)
    for row in greedy:
        n = int(row["cities"])
        normalized[n].append(row["distance"] / math.sqrt(n * KAGGLE_AREA))
        times[n].append(row["seconds"])
    sizes = sorted(normalized)
    figure, (left, right) = plt.subplots(1, 2, figsize=(13, 4.8))
    left.scatter([r["cities"] for r in greedy],
                 [r["distance"] / math.sqrt(r["cities"] * KAGGLE_AREA) for r in greedy],
                 s=4, alpha=0.25, color=COLORS["Greedy"], label="instâncias")
    left.plot(sizes, [statistics.mean(normalized[n]) for n in sizes], color="black",
              label="média por tamanho")
    left.axhline(BHH_CONSTANT, color="gray", linestyle="--", label="Ótimo assintótico (BHH)")
    left.set(xlabel="Cidades", ylabel="Distância / √(n·área)",
             title=f"Guloso nas {len(greedy)} instâncias da base")
    left.legend(fontsize=8)
    right.plot(sizes, [statistics.mean(times[n]) * 1000 for n in sizes], color=COLORS["Greedy"])
    right.set(xlabel="Cidades", ylabel="Milissegundos (média)", title="Tempo médio do guloso")
    for axis in (left, right):
        axis.grid(alpha=0.3)
    save_figure(figure, output / "graphs" / "E5_greedy_full_dataset.png")
    table = []
    for low, high in [(low, low + 9) for low in range(20, 100, 10)] + [(100, 100)]:
        values = [v for n in sizes if low <= n <= high for v in normalized[n]]
        spent = [v for n in sizes if low <= n <= high for v in times[n]]
        if len(values) > 1:
            table.append([f"{low}–{high}" if low != high else str(low), str(len(values)),
                          fmt(statistics.mean(values), ".3f"), fmt(statistics.stdev(values), ".3f"),
                          fmt(statistics.mean(spent) * 1000, ".2f")])
    write_table(output / "tables" / "E5.md", "E5 — Guloso em toda a base", [],
                ["Cidades", "Instâncias", "Distância/√(n·área) média", "Desvio",
                 "Tempo médio (ms)"], table, "rrrrr")
    total = sum(r["seconds"] for r in greedy)
    return [f"{len(greedy)} instâncias resolvidas pelo guloso em {duration(total)} no total "
            f"(média {fmt(total / len(greedy) * 1000, '.2f')} ms por instância)."]


def report_e6(rows, output) -> list[str]:
    convergence = load_csv(output / "data" / "E6_convergence.csv")
    figure, (curves, spread) = plt.subplots(1, 2, figsize=(13, 4.8))
    labels = sorted({r["instance"] for r in rows}, key=lambda label: _size(rows, label))
    table, summary = [], []
    for index, label in enumerate(labels):
        greedy = _find(rows, "Greedy", "instance", label, "distance")
        runs = defaultdict(dict)
        for point in convergence:
            if point["instance"] == label:
                runs[point["seed"]][int(point["generation"])] = point["best"] / greedy
        generations = sorted(next(iter(runs.values())))
        matrix = np.array([[run[g] for g in generations] for run in runs.values()])
        color = plt.cm.viridis(index / max(len(labels) - 1, 1))
        n = _size(rows, label)
        curves.plot(generations, np.median(matrix, axis=0), color=color, label=f"{n} cidades")
        curves.fill_between(generations, matrix.min(axis=0), matrix.max(axis=0), color=color,
                            alpha=0.2)
        genetic = [r for r in rows if r["instance"] == label and r["algorithm"] == "Genetic"]
        finals = [r["vs_greedy"] for r in genetic]
        distances = [r["distance"] for r in genetic]
        spread.boxplot(finals, positions=[index], widths=0.5)
        cv = statistics.stdev(distances) / statistics.mean(distances) * 100
        table.append([f"{label} ({n})", fmt(greedy), fmt(statistics.mean(distances)),
                      fmt(min(distances)), fmt(max(distances)), fmt(cv, ".2f"),
                      fmt(statistics.mean(finals), "+.1f"),
                      fmt(statistics.mean(r["seconds"] for r in genetic), ".2f")])
        summary.append(f"{n} cidades: AG {fmt(statistics.mean(finals), '+.1f')}% vs guloso em "
                       f"média; variação entre sementes (CV) {fmt(cv, '.2f')}%.")
    curves.axhline(1, color=COLORS["Greedy"], linestyle="--", label="Guloso")
    curves.set(ylim=(0.8, 1.6), xlabel="Geração", ylabel="Melhor distância / guloso",
               title="Convergência do AG (mediana e faixa de 10 sementes)")
    spread.axhline(0, color=COLORS["Greedy"], linestyle="--")
    spread.set_xticks(range(len(labels)), [f"{_size(rows, l)} cidades" for l in labels])
    spread.set(ylabel="AG vs guloso (%)", title="Resultado final por semente")
    for axis in (curves, spread):
        axis.grid(alpha=0.3)
    curves.legend(fontsize=8)
    save_figure(figure, output / "graphs" / "E6_ga_seeds.png")
    write_table(output / "tables" / "E6.md", "E6 — AG com 10 sementes", [],
                ["Instância (cidades)", "Guloso", "AG média", "AG melhor", "AG pior", "CV (%)",
                 "AG vs guloso (%)", "AG (s)"], table, "lrrrrrrr")
    return summary


def report_e7(rows, output) -> list[str]:
    genetic = sorted(by_algorithm(rows, "Genetic"), key=lambda r: r["cities"])
    greedy = {r["instance"]: r for r in by_algorithm(rows, "Greedy")}
    figure, (gain, times) = plt.subplots(1, 2, figsize=(13, 4.8))
    gain.scatter([r["cities"] for r in genetic], [r["vs_greedy"] for r in genetic],
                 color=COLORS["Genetic"], label="Genético")
    gain.axhline(0, color=COLORS["Greedy"], linestyle="--", label="Guloso")
    gain.set(xlabel="Cidades", ylabel="AG vs guloso (%)",
             title="101 a 149 cidades (2º CSV do Kaggle)")
    for algorithm, data in (("Genetic", genetic),
                            ("Greedy", sorted(greedy.values(), key=lambda r: r["cities"]))):
        times.plot([r["cities"] for r in data], [r["seconds"] for r in data], marker=".",
                   color=COLORS[algorithm], label=NAMES[algorithm])
    times.set(yscale="log", xlabel="Cidades", ylabel="Segundos (log)", title="Tempo de execução")
    for axis in (gain, times):
        axis.grid(alpha=0.3)
        axis.legend()
    save_figure(figure, output / "graphs" / "E7_kaggle_101_149.png")
    table = [[r["instance"], str(int(r["cities"])), fmt(greedy[r["instance"]]["distance"]),
              fmt(r["distance"]), fmt(r["vs_greedy"], "+.1f"), fmt(r["seconds"], ".2f")]
             for r in genetic]
    write_table(output / "tables" / "E7.md", "E7 — 101 a 149 cidades (tsp_instances_dataset.csv)",
                ["Identificação pela linha do arquivo: os nomes da coluna TSP_Instance não "
                 "correspondem às instâncias reais do TSPLIB."],
                ["Instância", "Cidades", "Guloso", "AG", "AG vs guloso (%)", "AG (s)"],
                table, "lrrrrr")
    values = [r["vs_greedy"] for r in genetic]
    return [f"{len(values)} instâncias: AG melhor em {sum(v < 0 for v in values)}; média "
            f"{fmt(statistics.mean(values), '+.1f')}% (de {fmt(min(values), '+.1f')}% a "
            f"{fmt(max(values), '+.1f')}%)."]


def report_e8(rows, output) -> list[str]:
    genetic = sorted(by_algorithm(rows, "Genetic"), key=lambda r: r["cities"])
    greedy = {r["instance"]: r for r in by_algorithm(rows, "Greedy")}
    labels = [r["instance"] for r in genetic]
    positions = np.arange(len(labels))
    figure, (gaps, trend) = plt.subplots(1, 2, figsize=(15, 5),
                                         gridspec_kw={"width_ratios": [2, 1]})
    gaps.bar(positions - 0.2, [r["gap_reference"] for r in genetic], 0.4,
             color=COLORS["Genetic"], label="Genético")
    gaps.bar(positions + 0.2, [greedy[l]["gap_reference"] for l in labels], 0.4,
             color=COLORS["Greedy"], label="Guloso")
    gaps.set_xticks(positions, [f"{l}\n({int(r['cities'])})" for l, r in zip(labels, genetic)],
                    rotation=90, fontsize=8)
    gaps.set(ylabel="% acima do ótimo publicado", title="TSPLIB: distância até o ótimo conhecido")
    trend.scatter([r["cities"] for r in genetic], [r["gap_reference"] for r in genetic],
                  color=COLORS["Genetic"], label="Genético")
    trend.scatter([greedy[l]["cities"] for l in labels],
                  [greedy[l]["gap_reference"] for l in labels], color=COLORS["Greedy"],
                  label="Guloso")
    trend.set(xlabel="Cidades", ylabel="% acima do ótimo", title="Gap em função do tamanho")
    for axis in (gaps, trend):
        axis.grid(alpha=0.3, axis="y")
        axis.legend()
    save_figure(figure, output / "graphs" / "E8_tsplib.png")
    table = [[l, str(int(r["cities"])), fmt(r["reference"], ".0f"),
              fmt(greedy[l]["distance"], ".0f"), fmt(greedy[l]["gap_reference"], "+.1f"),
              fmt(r["distance"], ".0f"), fmt(r["gap_reference"], "+.1f"), fmt(r["seconds"], ".1f")]
             for l, r in zip(labels, genetic)]
    write_table(output / "tables" / "E8.md", "E8 — TSPLIB com ótimo publicado",
                ["Distâncias pela definição oficial do TSPLIB (EUC_2D arredondada; ATT em att48)."],
                ["Instância", "Cidades", "Ótimo", "Guloso", "Guloso gap (%)", "AG", "AG gap (%)",
                 "AG (s)"], table, "lrrrrrrr")
    small = [r["gap_reference"] for r in genetic if r["cities"] <= 100]
    large = [r["gap_reference"] for r in genetic if r["cities"] > 200]
    greedy_gaps = [g["gap_reference"] for g in greedy.values()]
    wins = sum(r["gap_reference"] < greedy[r["instance"]]["gap_reference"] for r in genetic)
    return [f"Guloso: gap médio {fmt(statistics.mean(greedy_gaps), '.1f')}% acima do ótimo; "
            f"AG: {fmt(statistics.mean(r['gap_reference'] for r in genetic), '.1f')}%. "
            f"AG melhor que o guloso em {wins}/{len(genetic)} instâncias.",
            f"AG até 100 cidades: gap médio {fmt(statistics.mean(small), '.1f')}%; acima de 200 "
            f"cidades: {fmt(statistics.mean(large), '.1f')}% (mesmas 1.500 gerações)."]


# ---------------------------------------------------------------- resumo docs/README.md

EXPERIMENT_SECTIONS = (
    ("E1", "Crescimento da força bruta", "E1_brute_force_growth.png", report_e1,
     "Quanto custa garantir o ótimo? Força bruta de 4 a 12 cidades e projeção de O(n!)."),
    ("E2", "Gap até o ótimo exato", "E2_exact_gap.png", report_e2,
     "Em 20 instâncias de 10 cidades, quanto o AG e o guloso ficam acima do ótimo?"),
    ("E3", "Todos os tamanhos da base", "E3_all_sizes.png", report_e3,
     "Como qualidade e tempo evoluem de 20 a 100 cidades (81 tamanhos)?"),
    ("E4", "Variação entre instâncias", "E4_instance_variability.png", report_e4,
     "A vantagem do AG se mantém em instâncias diferentes do mesmo tamanho?"),
    ("E5", "Guloso em toda a base", "E5_greedy_full_dataset.png", report_e5,
     "Visão das 2.783 instâncias com o algoritmo mais barato."),
    ("E6", "AG com 10 sementes", "E6_ga_seeds.png", report_e6,
     "O AG é estável? Como ele converge ao longo das gerações?"),
    ("E7", "101 a 149 cidades", "E7_kaggle_101_149.png", report_e7,
     "O comportamento se mantém acima de 100 cidades (segundo CSV do Kaggle)?"),
    ("E8", "TSPLIB com ótimo publicado", "E8_tsplib.png", report_e8,
     "Em instâncias clássicas de 48 a 442 cidades, quão longe do ótimo real ficamos?"),
)


def build_docs(output: Path = DOCS_DIR, brute_timeout: float = 600) -> Path:
    """Gera tabelas, gráficos e docs/README.md a partir dos CSVs já salvos."""
    lines = ["# Resultados", "",
             "Gerado por `python benchmarks.py`. Cada algoritmo roda uma vez por instância, na "
             "mesma máquina; o AG usa a configuração padrão de `genetic.py` (população 200, "
             "1.500 gerações).", ""]
    findings = render_benchmark(output, brute_timeout)
    if findings:
        lines += ["## Benchmark principal", "", "![Comparação](graphs/comparison.png)", ""]
        lines += [f"- {finding}" for finding in findings]
        lines += ["", "Tabela: [tables/benchmark.md](tables/benchmark.md) · dados: "
                  "[data/benchmark.csv](data/benchmark.csv)", ""]
    gifs = sorted((output / "gifs").glob("*.gif"))
    if gifs:
        lines += ["## GIFs", ""] + [f"- [{gif.name}](gifs/{gif.name})" for gif in gifs] + [""]
    for key, title, image, reporter, question in EXPERIMENT_SECTIONS:
        rows = load_csv(output / "data" / f"{key}.csv")
        if not rows:
            continue
        lines += [f"## {key} — {title}", "", f"*{question}*", "", f"![{title}](graphs/{image})", ""]
        lines += [f"- {finding}" for finding in reporter(rows, output)]
        lines += ["", f"Tabela: [tables/{key}.md](tables/{key}.md) · dados: "
                  f"[data/{key}.csv](data/{key}.csv)", ""]
    readme = output / "README.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme
