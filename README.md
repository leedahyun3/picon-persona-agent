# PICon Persona Agent + Evaluator

이 저장소는 두 가지를 함께 제공합니다.

- `PICon이 직접 호출할 수 있는 persona agent server`
- `로컬에서 IC / EC / RC를 확인하는 evaluator demo`

## 왜 이 구성이 중요한가

PICon 과제에서 핵심은 단순 챗봇이 아니라, 심문형 질문에도 자기모순 없이 버티는 `강건한 persona agent`입니다. 이 저장소는 팀원 방식의 OpenAI 호환 API 서버 형태를 따르면서도, 다음을 강화했습니다.

- fact sheet 기반 고정 사실 관리
- 세션별 canonical answer 재사용
- 메타 누출 방지
- 확인 질문과 반복 질문에 대한 안정 응답
- 임의의 물리적 디테일 요구에는 무리하게 발명하지 않는 bounded response

## 설치

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Persona Agent Server 실행

```bash
python3 root_cli.py serve-agent --host 0.0.0.0 --port 8001
```

헬스체크:

```bash
curl http://127.0.0.1:8001/health
```

OpenAI 호환 호출 예시:

```bash
curl http://127.0.0.1:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "PersonaAgent",
    "messages": [
      {"role": "user", "content": "What is your current job?"}
    ]
  }'
```

PICon에서는 `http://<host>:<port>/v1` 를 `api_base`로 사용할 수 있습니다.

## Evaluator Demo 실행

```bash
python3 root_cli.py run-demo
python3 root_cli.py serve-eval --port 8080
```

브라우저에서 `http://127.0.0.1:8080` 으로 접속하면 세션 실행과 점수 확인이 가능합니다.

## 주요 파일

- `template_server.py`: FastAPI 기반 persona agent server
- `persona_agent/`: fact sheet, parser, session memory, response engine
- `data/persona_worker.json`: 강건한 응답을 위한 grounded persona facts
- `picon_eval/`: 로컬 evaluator demo
- `render.yaml`, `vercel.json`: 원격 배포 설정

## 배포

Render:

```bash
render blueprint uses render.yaml
```

Vercel:

- `app.py` 가 ASGI entrypoint 입니다.
- `api/index.py` 가 라우팅 진입점입니다.

## 현재 상태

- 로컬 evaluator 실행 가능
- PICon 호출용 `/health`, `/v1/chat/completions` 엔드포인트 제공
- GitHub/Render/Vercel 업로드용 파일 포함
