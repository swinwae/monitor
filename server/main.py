from fastapi import FastAPI

app = FastAPI(title="Monitor")


@app.get("/api/health")
def health():
    return {"status": "ok"}
