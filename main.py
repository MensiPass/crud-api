from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from sqlmodel import Field,SQLModel, create_engine,Session,select
import os, psycopg
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

#connect to database from enviromental variables
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"))

#task table in DB
class Tasks (SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    done: bool = False
class TaskCreate(BaseModel):
    title: str
class TaskUpdate(BaseModel):
    title: str
    done: bool


#seed initial data
def create_db_and_seed():
    with Session(engine) as session:
        tasks = session.exec(select(Tasks)).all()

        if not tasks:
            example_tasks = [
                Tasks(title="Learn FastAPI", done=False),
                Tasks(title="Learn PostgreSQL", done=False),
                Tasks(title="Build CRUD API", done=False),
            ]

            session.add_all(example_tasks)
            session.commit()
create_db_and_seed()

@app.get("/", description="Returns information about the Task API")
def api_info():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }
@app.get("/health",description="Checks app health", status_code=200)
def app_health():
    return { "status": "ok" }

@app.get("/tasks",description="Returns all tasks", status_code=200)
def app_info():
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM tasks")
            rows = cursor.fetchall()

            tasks = []

            for row in rows:
                tasks.append({
                    "id": row[0],
                    "title": row[1],
                    "done": row[2]
                })

        return tasks
    
@app.get("/tasks/{id}", description="Returns specific task", status_code=200)
def get_task(id: int):
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM tasks WHERE id = %s",
                (id,)
            )

            row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="error: Task not found"
        )

    return {
        "id": row[0],
        "title": row[1],
        "done": row[2]
    }

@app.post("/tasks", description="Adds new task", status_code=201)
def post_task(task: TaskCreate):
    if not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Task title is missing or empty"
        )

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (title, done)
                VALUES (%s, %s)
                RETURNING id, title, done
                """,
                (task.title, False)
            )

            row = cursor.fetchone()

    new_task = {
        "id": row[0],
        "title": row[1],
        "done": row[2]
    }

    return {
        "message": "Task added",
        "tasks": new_task
    }

@app.put("/tasks/{id}", description="Updates specific task", status_code=200)
def put_task(id: int, utask: TaskUpdate):

    if utask.title is not None:
        if not utask.title.strip():
            raise HTTPException(
                status_code=400,
                detail="Task title cannot be empty"
            )

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:

            # Check if task exists
            cursor.execute(
                "SELECT id, title, done FROM tasks WHERE id = %s",
                (id,)
            )

            task = cursor.fetchone()

            if task is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Task {id} not found"
                )

            # Update the task
            cursor.execute(
                """
                UPDATE tasks
                SET title = %s,
                    done = %s
                WHERE id = %s
                RETURNING id, title, done
                """,
                (
                    utask.title,
                    utask.done,
                    id
                )
            )

            row = cursor.fetchone()

    return {
        "id": row[0],
        "title": row[1],
        "done": row[2]
    }

@app.delete("/tasks/{id}", description="Deletes specific task", status_code=204)
def del_task(id: int):
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                "DELETE FROM tasks WHERE id = %s RETURNING id",
                (id,)
            )

            row = cursor.fetchone()

            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="error: Task with specified id is missing"
                )