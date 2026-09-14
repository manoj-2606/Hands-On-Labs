from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hands-On 16 — Hardened and Secured"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/secret")
def secret():
    # Reads secret mounted from Azure Key Vault via CSI driver
    secret_path = "/mnt/secrets/db-password"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            return {"secret_mounted": True, "value": f.read().strip()}
    return {"secret_mounted": False}