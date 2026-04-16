FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 8001

CMD ["python3", "root_cli.py", "serve-agent", "--host", "0.0.0.0", "--port", "8001"]
