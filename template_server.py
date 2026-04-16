from __future__ import annotations

import argparse
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from persona_agent import FactSheet, FactSheetError, PersonaEngine


app = FastAPI(title="PICon Persona Agent")
engine: PersonaEngine | None = None
agent_name = "PersonaAgent"


def _default_fact_sheet_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "persona_worker.json"


def initialize_engine(path: str | Path | None = None, name: str = "PersonaAgent") -> None:
    global engine
    global agent_name
    fact_sheet = FactSheet.load(path or _default_fact_sheet_path())
    engine = PersonaEngine(fact_sheet)
    agent_name = name or fact_sheet.display_name


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": agent_name}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        return JSONResponse(status_code=400, content={"error": "No messages provided"})

    if engine is None:
        initialize_engine()

    try:
        assert engine is not None
        content, trace = engine.respond(messages)
    except FactSheetError as error:
        return JSONResponse(status_code=500, content={"error": str(error)})
    except Exception as error:
        return JSONResponse(status_code=500, content={"error": str(error)})

    created = int(time.time())
    return {
        "id": f"chatcmpl-{created}",
        "object": "chat.completion",
        "created": created,
        "model": body.get("model") or agent_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "trace": trace,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PICon-compatible persona agent server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--fact-sheet", default=str(_default_fact_sheet_path()))
    parser.add_argument("--name", default="PersonaAgent")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    initialize_engine(args.fact_sheet, args.name)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
