from __future__ import annotations

import argparse
from collections import defaultdict

from rummiplus import BotConfig, SimulationConfig, run_simulation


def run_single_match(levels: list[int], randomness: float, seed: int, max_turns: int) -> None:
    bot_configs = [
        BotConfig(level=level, randomness=randomness, seed=seed + idx * 17)
        for idx, level in enumerate(levels)
    ]
    result = run_simulation(SimulationConfig(bot_configs=bot_configs, seed=seed, max_turns=max_turns))

    print("=" * 88)
    print(f"Partida seed={seed} niveles={levels} aleatoriedad={randomness:.2f}")
    print("-" * 88)
    for line in result.logs:
        print(line)
    print("-" * 88)
    if result.winner_id:
        print(f"Ganador: {result.winner_id} en {result.turns_played} turnos")
    else:
        print(f"Sin ganador tras {result.turns_played} turnos")
    print("Puntos finales en rack (menos es mejor):")
    for bot_id, points in sorted(result.final_rack_points.items(), key=lambda x: x[1]):
        print(f"  - {bot_id}: {points}")


def run_tournament(levels: list[int], randomness: float, games: int, max_turns: int) -> None:
    wins = defaultdict(int)
    points_sum = defaultdict(int)

    for game_idx in range(games):
        seed = 7000 + game_idx * 31
        bot_configs = [
            BotConfig(level=level, randomness=randomness, seed=seed + i * 13)
            for i, level in enumerate(levels)
        ]
        result = run_simulation(
            SimulationConfig(
                bot_configs=bot_configs,
                seed=seed,
                max_turns=max_turns,
            )
        )
        if result.winner_id:
            wins[result.winner_id] += 1
        for bot_id, points in result.final_rack_points.items():
            points_sum[bot_id] += points

    print("=" * 88)
    print(f"Torneo de {games} partidas | niveles={levels} | aleatoriedad={randomness:.2f}")
    print("-" * 88)
    for idx, _ in enumerate(levels):
        bot_id = f"Bot-{idx+1}"
        avg_points = points_sum[bot_id] / games
        print(f"{bot_id}: victorias={wins[bot_id]:3d} | puntos medios={avg_points:7.2f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo de bots Rummikub (nivel 1-10 + aleatoriedad configurable)."
    )
    parser.add_argument("--levels", default="2,5,9", help="Niveles separados por coma. Ej: 1,5,10")
    parser.add_argument("--randomness", type=float, default=0.25, help="Aleatoriedad [0..1]")
    parser.add_argument("--seed", type=int, default=1234, help="Seed para partida de ejemplo")
    parser.add_argument("--max-turns", type=int, default=120, help="Turnos máximos por partida")
    parser.add_argument("--games", type=int, default=50, help="Partidas del torneo comparativo")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]
    levels = [max(1, min(10, lvl)) for lvl in levels]
    randomness = max(0.0, min(1.0, args.randomness))

    run_single_match(levels, randomness, args.seed, args.max_turns)
    run_tournament(levels, randomness, args.games, args.max_turns)


if __name__ == "__main__":
    main()
