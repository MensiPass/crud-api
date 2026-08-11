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

tids=[]
@app.get("/", description="Returns information about the Task API")
def api_info():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }

@app.get("/tasks",description="Returns all tasks")
async def app_info():
    return tasks

@app.get("/tasks/{id}",description="Returns specific task")
def get_task(id: int):
    #search task with id
    for task in tasks:
        if task["id"]==id:
            return task
    raise HTTPException(status_code=404, detail="error:"  f"Task {id} not found")

@app.post("/tasks",description="Adds new task")
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

@app.put("/tasks/{id}",description="Updates specific task")
def put_task(utask: Task ):
    #search task with id
    for task in tasks:
        tids.append(task["id"])
    if not utask.id and not utask.title.strip() and not tids.includes(utask.id):
        raise HTTPException(status_code=404, detail="error:" "Task title is missing or empty")
    else:
        for task in tasks:
            if task["id"]==utask.id:
                task["title"]=utask.title
                if utask.done:  
                    task["done"]=utask.done 
        return {"message": "New task updated", "tasks": tasks}
   
@app.delete("/tasks/{id}",description="Deletes specific task")
def del_task(id: int ):
    #search task with id
    for task in tasks:
        if task["id"]==id:
            tasks.remove(task)
            return {"message": "New task list without deleted task", "tasks": tasks}
    raise HTTPException(status_code=404, detail="error:" "Task with specified id is missing")