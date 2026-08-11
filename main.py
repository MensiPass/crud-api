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

@app.get("/")
def api_info():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }

@app.get("/tasks")
async def app_info():
    return tasks

@app.get("/tasks/{id}")
def get_task(id: int):
    #search task with id
    for task in tasks:
        if task["id"]==id:
            return task
    raise HTTPException(status_code=404, detail="error:"  f"Task {id} not found")

@app.post("/tasks")
def post_task(task_title: str ):
    #search task with id
    if task_title and task_title.strip():
        new_task = {
            "id": len(tasks) + 1,
            "title": task_title,
            "done": False
            }
        tasks.append(new_task)
        return {"message": "New task added", "tasks": new_task}
    else:
        raise HTTPException(status_code=404, detail="error:" "Task title is missing or empty")

       