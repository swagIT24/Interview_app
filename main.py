import os
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from database.connections import init_db
from routes import interviwe, auth, voice, resume, jobs, roleplay, profile_setup, dashboard, plan
from services.limiter import limiter

MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request too large"}
            )
        return await call_next(request)

app = FastAPI()

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down."}
    )
)

app.add_exception_handler(
    RequestValidationError,
    lambda request, exc: JSONResponse(
        status_code=422,
        content={"detail": [{"field": e["loc"][-1], "message": e["msg"]} for e in exc.errors()]}
    )
)

app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(SlowAPIMiddleware)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

init_db()

app.include_router(interviwe.router)
app.include_router(auth.router)
app.include_router(voice.router)
app.include_router(resume.router)
app.include_router(jobs.router)
app.include_router(roleplay.router)
app.include_router(profile_setup.router)
app.include_router(dashboard.router)
app.include_router(plan.router)


app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def serve_home():
    return FileResponse("frontend/index.html")

@app.get("/landing")
def serve_landing():
    return FileResponse("frontend/landing.html")

@app.get("/register")
def serve_register():
    return FileResponse("frontend/register.html")

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

@app.get("/goal-setting")
def serve_goal_setting():
    return FileResponse("frontend/goal-setting.html")

@app.get("/favicon.ico")
def favicon():
    return Response(content=b'', media_type='image/x-icon')
# to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload

#to activate venv : source venv/bin/activate
# to run app : python -m uvicorn main:app --reload

#261885335630