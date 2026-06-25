#!/usr/bin/env python3

import argparse
import sys

from app.server import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Word Template Generator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Starting on http://{args.host}:{args.port}", flush=True)
    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
