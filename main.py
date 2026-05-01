from fastapi import FastAPI
from routes import interviwe
from database.connections import *
from routes import auth
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


init_db()


app.include_router(interviwe.router)
app.include_router(auth.router)

migrate_schema()

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def serve_home():
    return FileResponse("frontend/index.html")

#to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload
