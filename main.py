from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from sqlmodel import Field,SQLModel, create_engine,Session,select

app = FastAPI()

#create database
DATABASE_URL="sqlite:///tasks.db"

engine=create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  
)
#tasks = [{"id": 1,"title": "Learn FastAPI","done": False},{"id": 2,"title": "Build Task API","done": False}, {"id": 3, "title": "Push project to GitHub", "done": True }]
#task table in DB
class Task (SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    done: bool = False

tids=[]

#enter initial tasks in DB, only if none present
def create_db_and_seed():
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()

        if not tasks:
            example_tasks = [
                Task(title="Learn FastAPI", done=False),
                Task(title="Learn SQLite", done=False),
                Task(title="Build CRUD API", done=False),
            ]

            session.add_all(example_tasks)
            session.commit()


create_db_and_seed()
# temp data for tasks
class TaskCreate(BaseModel):
    title: str
class TaskUpdate(BaseModel):
    title: str
    done: bool

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
    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()
        return tasks
    
@app.get("/tasks/{id}", description="Returns specific task", status_code=200)
def get_task(id: int):
    with Session(engine) as session:
        task = session.get(Task, id)

        if task is None:
            raise HTTPException(
                status_code=404,
                detail="error: Task not found"
            )

        return task

@app.post("/tasks", description="Adds new task", status_code=201)
def post_task(task: TaskCreate):
    if not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Task title is missing or empty"
        )

    new_task = Task(
        title=task.title,
        done=False
    )

    with Session(engine) as session:
        session.add(new_task)
        session.commit()
        session.refresh(new_task)

    return {"message": "Task added", "tasks": new_task}

@app.put("/tasks/{id}", description="Updates specific task", status_code=200)
def put_task(id: int, utask: TaskUpdate):
    with Session(engine) as session:
        task = session.get(Task, id)

        if task is None:
            raise HTTPException(
                status_code=404,
                detail=f"Task {id} not found"
            )

        if utask.title is not None:
            if not utask.title.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Task title cannot be empty"
                )
            task.title = utask.title

        if utask.done is not None:
            task.done = utask.done

        session.add(task)
        session.commit()
        session.refresh(task)

        return task

@app.delete("/tasks/{id}",description="Deletes specific task",status_code=204)
def del_task(id: int):
    with Session(engine) as session:
        task = session.get(Task, id)

        if task is None:
            raise HTTPException(
                status_code=404,
                detail="error: Task with specified id is missing"
            )

        session.delete(task)
        session.commit()