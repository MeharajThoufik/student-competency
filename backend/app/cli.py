"""Command-line tasks against DATABASE_URL.

    python -m app.cli seed-synthetic --learners 200 --seed 42
    python -m app.cli clear-synthetic
"""

import argparse

from app.core.db import get_sessionmaker
from app.services import synthetic


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed-synthetic", help="Replace synthetic learners with a fresh deterministic set")
    seed.add_argument("--learners", type=int, default=200)
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--months", type=int, default=24)
    sub.add_parser("clear-synthetic", help="Delete all synthetic learners")
    args = parser.parse_args()

    factory = get_sessionmaker()
    if factory is None:
        raise SystemExit("DATABASE_URL is not set")
    with factory() as db:
        if args.command == "seed-synthetic":
            counts = synthetic.generate(db, learners=args.learners, seed=args.seed, months=args.months)
            print(f"Created {sum(counts.values())} synthetic learners: {counts}")
        else:
            print(f"Deleted {synthetic.delete_synthetic(db)} synthetic learners")


if __name__ == "__main__":
    main()
