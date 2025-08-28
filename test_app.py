from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Test App")

@app.get("/")
def read_root():
    return JSONResponse(content={"message": "Test app is running correctly"})
