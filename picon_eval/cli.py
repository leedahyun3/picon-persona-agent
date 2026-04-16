from __future__ import annotations

import argparse
import json

from picon_eval.runner import run_demo
from picon_eval.server import serve


def run_demo_command() -> int:
    result = run_demo()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def serve_eval_command(host: str, port: int) -> int:
    serve(host, port)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PICon persona evaluation app")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run-demo", help="Run the bundled demo evaluation session")

    serve_parser = subparsers.add_parser("serve", help="Run the local web app")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8080, type=int)

    args = parser.parse_args()

    if args.command == "run-demo":
        return run_demo_command()
    if args.command == "serve":
        return serve_eval_command(args.host, args.port)
    return 1
