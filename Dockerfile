FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install "fastapi[standard]" sqlmodel psycopg[binary] python-dotenv

CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]