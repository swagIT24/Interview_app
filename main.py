from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database.connections import init_db, migrate_schema
from routes import interviwe, auth, voice, resume, jobs, roleplay

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
app.include_router(jobs.router)
app.include_router(roleplay.router)

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

@app.get("/practice")
def serve_practice():
    return FileResponse("frontend/practice.html")

@app.get("/progress")
def serve_progress():
    return FileResponse("frontend/progress.html")

@app.get("/profile")
def serve_profile():
    return FileResponse("frontend/profile.html")

@app.get("/jobs-tracker")
def serve_jobs():
    return FileResponse("frontend/jobs.html")

@app.get("/favicon.ico")
def favicon():
    return Response(content=b'', media_type='image/x-icon')
# to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload

#to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload

#261885335630