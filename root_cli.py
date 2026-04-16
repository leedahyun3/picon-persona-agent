from __future__ import annotations

import argparse

from picon_eval.cli import run_demo_command, serve_eval_command
import template_server


def main() -> int:
    parser = argparse.ArgumentParser(description="PICon evaluator and persona agent server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run-demo", help="Run the bundled evaluator demo")

    eval_parser = subparsers.add_parser("serve-eval", help="Run the local evaluator UI")
    eval_parser.add_argument("--host", default="127.0.0.1")
    eval_parser.add_argument("--port", type=int, default=8080)

    agent_parser = subparsers.add_parser("serve-agent", help="Run the PICon-callable persona agent server")
    agent_parser.add_argument("--host", default="0.0.0.0")
    agent_parser.add_argument("--port", type=int, default=8001)
    agent_parser.add_argument("--fact-sheet", default="data/persona_worker.json")
    agent_parser.add_argument("--name", default="PersonaAgent")

    args = parser.parse_args()

    if args.command == "run-demo":
        return run_demo_command()
    if args.command == "serve-eval":
        return serve_eval_command(args.host, args.port)
    if args.command == "serve-agent":
        template_server.initialize_engine(args.fact_sheet, args.name)
        import uvicorn

        uvicorn.run(template_server.app, host=args.host, port=args.port)
        return 0
    return 1
