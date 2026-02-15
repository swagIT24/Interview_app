from fastapi import FastAPI
from routes import interviwe
from database.connections import *

app = FastAPI()
init_db()
app.include_router(interviwe.router)

init_db()
migrate_schema()