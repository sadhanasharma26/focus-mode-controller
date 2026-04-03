"""Application entry point for Focus Mode Controller."""

import argparse
import os

from app import create_app
from app.database import init_db, seed_demo_history
from app.timer import scheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.demo:
        os.environ["FOCUS_DEMO_MODE"] = "1"

    app = create_app(demo_mode=args.demo)
    init_db()

    if args.demo:
        inserted = seed_demo_history(days=21)
        if inserted:
            print(f"[focus-mode] demo history seeded: {inserted} sessions")

    if not scheduler.running:
        scheduler.start()

    app.run(port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
