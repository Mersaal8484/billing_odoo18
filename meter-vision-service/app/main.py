import os

from fastapi import Depends, FastAPI, Header, HTTPException

from .inference import analyze
from .schemas import InferenceRequest, InferenceResponse

app = FastAPI(title="Meter Vision Service", version="0.1.0")


def verify_token(authorization: str | None = Header(default=None)):
    expected = os.getenv("METER_VISION_API_TOKEN", "")
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid service token")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "meter-vision-service", "model": os.getenv("METER_VISION_MODEL", "baseline-ocr")}


@app.post("/v1/inference", response_model=InferenceResponse, dependencies=[Depends(verify_token)])
def inference(request: InferenceRequest):
    try:
        return analyze(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
