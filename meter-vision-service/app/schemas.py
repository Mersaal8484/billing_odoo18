from typing import Optional

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    image_base64: str = Field(min_length=1)
    meter_id: Optional[str] = None
    meter_type_hint: Optional[str] = None
    language_hint: str = "eng"


class ConfidenceValue(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class QualityResult(BaseModel):
    state: str
    score: float
    width: int
    height: int


class PipelineStage(BaseModel):
    name: str
    state: str
    confidence: float = 0.0
    weights_status: str = "not_ready"


class InferenceResponse(BaseModel):
    request_id: str
    state: str
    model: str
    model_version: str
    quality: QualityResult
    meter_number: ConfidenceValue = ConfidenceValue()
    reading: ConfidenceValue = ConfidenceValue()
    raw_text: str = ""
    flags: list[str] = []
    stages: list[PipelineStage] = []
    auto_approval_eligible: bool = False
    error_message: Optional[str] = None
