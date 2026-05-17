from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database.connections import init_db, migrate_schema
from routes import interviwe, auth, voice, resume

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
app.include_router(voice.router)
app.include_router(resume.router)

migrate_schema()

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def serve_home():
    return FileResponse("frontend/index.html")

@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("frontend/dashboard.html")

@app.get("/onboarding")
def serve_onboarding():
    return FileResponse("frontend/onboarding.html")

# to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload

#to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload

#261885335630