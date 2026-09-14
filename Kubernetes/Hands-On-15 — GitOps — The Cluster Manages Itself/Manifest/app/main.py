from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hands-On 15 — GitOps is live"}

@app.get("/health")
def health():
    return {"status": "ok"}