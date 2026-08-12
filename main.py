from fastapi import FastAPI,HTTPException
from pydantic import BaseModel

app = FastAPI()

# temp data for tasks
tasks = [
    {
        "id": 1,
        "title": "Learn FastAPI",
        "done": False
    },
    {
        "id": 2,
        "title": "Build Task API",
        "done": False
    },
    {
        "id": 3,
        "title": "Push project to GitHub",
        "done": True
    }
]

class Task(BaseModel):
    id: int
    title: str
    done: bool
class TaskCreate(BaseModel):
    title: str
class TaskUpdate(BaseModel):
    title: str
    done: bool

tids=[]
@app.get("/", description="Returns information about the Task API")
def api_info():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }
@app.get("/health",description="Checks app health", status_code=201)
def app_health():
    return { "status": "ok" }

@app.get("/tasks",description="Returns all tasks")
def app_info():
    return tasks

@app.get("/tasks/{id}",description="Returns specific task")
def get_task(id: int):
    #search task with id
    for task in tasks:
        if task["id"]==id:
            return task
    raise HTTPException(status_code=404, detail="error:"  f"Task {id} not found")

@app.post("/tasks",description="Adds new task",status_code=201)
def post_task(task: TaskCreate ):
    if not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Task title is missing or empty"
        )

    new_task = {
        "id": len(tasks) + 1,
        "title": task.title,
        "done": False
    }

    tasks.append(new_task)
    return {"message": "New task added", "tasks": new_task}

@app.put("/tasks/{id}",description="Updates specific task",status_code=200)
def put_task(id: int, utask: TaskUpdate ):
    for task in tasks:
        if task["id"] == id:
            if utask.title is not None:
                if not utask.title.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Task title cannot be empty"
                    )
                task["title"] = utask.title
            if utask.done is not None:
                task["done"] = utask.done
            return task
    raise HTTPException(
        status_code=404,
        detail=f"Task {id} not found"
    )
   
@app.delete("/tasks/{id}",description="Deletes specific task",status_code=204)
def del_task(id: int ):
    #search task with id
    for task in tasks:
        if task["id"]==id:
            tasks.remove(task)
            return {"message": "New task list without deleted task", "tasks": tasks}
    raise HTTPException(status_code=404, detail="error:" "Task with specified id is missing")