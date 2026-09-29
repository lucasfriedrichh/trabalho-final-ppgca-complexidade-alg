"""Gera animações das três abordagens em docs/gifs/, com as instâncias da base do Kaggle.

Uso: python generate_gifs.py --sizes 10 20 50 100
     python generate_gifs.py --sizes 10 --generations 300 --frames 12

Tamanhos menores que 20 usam as primeiras cidades da instância de 20 cidades.
A força bruta só é animada até 10 cidades, onde termina com o ótimo exato.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from brute_force import route_count, solve_brute_force
from genetic import GeneticConfig, solve_genetic
from greedy_tsp import solve_greedy
from util import Instance, Route, load_cases

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs" / "gifs"
SIZES = (10, 20, 50, 100)
MAX_BRUTE_FORCE_GIF_CITIES = 10
FRAME_MILLISECONDS = 220


def frame_from_figure(figure) -> Image.Image:
    """Copia o desenho do Matplotlib antes de reutilizar a figura."""
    figure.canvas.draw()
    width, height = figure.canvas.get_width_height()
    return Image.frombytes("RGBA", (width, height),
                           bytes(figure.canvas.buffer_rgba())).convert("RGB")


def draw_cities(axis, instance: Instance, title: str, subtitle: str) -> None:
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


def draw_edges(axis, instance: Instance, edges) -> None:
    for a, b in edges:
        (x1, y1), (x2, y2) = instance.coordinates[a], instance.coordinates[b]
        axis.plot([x1, x2], [y1, y2], color="#1967a3", linewidth=1.8, zorder=1)


def route_edges(route: Route) -> list[tuple[int, int]]:
    return [(route[i - 1], route[i]) for i in range(len(route))]


def save_gif(frames: list[Image.Image], output: Path) -> None:
    if not frames:
        raise ValueError("Nenhum quadro gerado")
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, save_all=True, append_images=frames[1:],
                   duration=FRAME_MILLISECONDS, loop=0, optimize=True)
    print(f"Criado: {output.relative_to(ROOT)} ({len(frames)} quadros)")


def sampled(items: list, max_frames: int) -> list:
    """Até max_frames itens espaçados, sempre com o primeiro e o último."""
    if len(items) <= max_frames:
        return items
    indexes = sorted({round(i * (len(items) - 1) / (max_frames - 1)) for i in range(max_frames)})
    return [items[i] for i in indexes]


def generate_greedy(instance: Instance, max_frames: int) -> None:
    accepted: list[tuple[int, int]] = []
    solution = solve_greedy(instance.distances, on_edge=lambda a, b: accepted.append((a, b)))
    steps = sampled(list(range(1, len(accepted) + 1)), max_frames)
    figure, axis = plt.subplots(figsize=(7, 5), dpi=90)
    try:
        frames = []
        for step in steps:
            done = step == len(accepted)
            subtitle = (f"{step}/{instance.size} arestas · distância: {solution.cost:.1f}"
                        if done else f"{step}/{instance.size} arestas, da menor para a maior")
            draw_cities(axis, instance, f"Guloso de arestas · {instance.label}", subtitle)
            draw_edges(axis, instance, accepted[:step])
            frames.append(frame_from_figure(figure))
        save_gif(frames, DOCS / f"greedy_{instance.size}.gif")
    finally:
        plt.close(figure)


def generate_genetic(instance: Instance, config: GeneticConfig, max_frames: int,
                     seed: int) -> None:
    history: list[tuple[int, Route, float]] = []
    solve_genetic(instance.distances, config, seed=seed + instance.size,
                  on_generation=lambda g, route, cost: history.append((g, route, cost)))
    costs = [cost for _, _, cost in history]
    figure, (route_axis, cost_axis) = plt.subplots(1, 2, figsize=(10, 4.8), dpi=90)
    try:
        frames = []
        for generation, route, cost in sampled(history, max_frames):
            draw_cities(route_axis, instance, f"Genético · {instance.label}",
                        f"Geração {generation}/{config.generations} · distância: {cost:.1f}")
            draw_edges(route_axis, instance, route_edges(route))
            cost_axis.clear()
            cost_axis.plot(range(1, generation + 1), costs[:generation], color="#16783c")
            cost_axis.set_xlim(1, max(config.generations, 2))
            margin = max((max(costs) - min(costs)) * 0.12, 1)
            cost_axis.set_ylim(min(costs) - margin, max(costs) + margin)
            cost_axis.set(title="Melhor distância por geração", xlabel="Geração",
                          ylabel="Distância")
            cost_axis.grid(alpha=0.2)
            figure.tight_layout()
            frames.append(frame_from_figure(figure))
        save_gif(frames, DOCS / f"genetic_{instance.size}.gif")
    finally:
        plt.close(figure)


def generate_brute_force(instance: Instance, max_frames: int) -> None:
    if instance.size > MAX_BRUTE_FORCE_GIF_CITIES:
        print(f"GIF de força bruta ignorado para {instance.size} cidades: "
              f"(n-1)!/2 = {route_count(instance.size):.3g} rotas.")
        return
    improvements: list[tuple[int, Route, float]] = []
    solution = solve_brute_force(
        instance.distances,
        on_improvement=lambda count, route, cost: improvements.append((count, route, cost)))
    total = route_count(instance.size)
    figure, axis = plt.subplots(figsize=(7, 5), dpi=90)
    try:
        frames = []
        for count, route, cost in sampled(improvements, max_frames):
            draw_cities(axis, instance, f"Força bruta · {instance.label}",
                        f"{count}/{total} rotas avaliadas · melhor distância: {cost:.1f}")
            draw_edges(axis, instance, route_edges(route))
            frames.append(frame_from_figure(figure))
        draw_cities(axis, instance, f"Força bruta · {instance.label}",
                    f"{total}/{total} rotas · ótimo: {solution.cost:.1f}")
        draw_edges(axis, instance, route_edges(solution.route))
        frames.append(frame_from_figure(figure))
        save_gif(frames, DOCS / f"brute_force_{instance.size}.gif")
    finally:
        plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES),
                        help="cidades por GIF (padrão: 10 20 50 100)")
    parser.add_argument("--generations", type=int, default=GeneticConfig().generations,
                        help="gerações do algoritmo genético")
    parser.add_argument("--frames", type=int, default=18,
                        help="número máximo aproximado de quadros por GIF (padrão: 18)")
    parser.add_argument("--seed", type=int, default=42,
                        help="semente do algoritmo genético (padrão: 42)")
    args = parser.parse_args()
    if args.generations < 1 or args.frames < 2:
        parser.error("--generations deve ser >= 1 e --frames deve ser >= 2")

    config = GeneticConfig(generations=args.generations)
    try:
        cases = load_cases(tuple(dict.fromkeys(args.sizes)))
    except ValueError as exc:
        parser.error(str(exc))
    for instance in cases:
        generate_greedy(instance, args.frames)
        generate_genetic(instance, config, args.frames, args.seed)
        generate_brute_force(instance, args.frames)


if __name__ == "__main__":
    main()
