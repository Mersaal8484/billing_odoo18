from typing import Optional

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    image_base64: str = Field(min_length=1)
    meter_id: Optional[str] = None
    meter_type_hint: Optional[str] = None
    language_hint: str = "eng"
    # Pixel coordinates on the original image.  The service intentionally
    # accepts a confirmed display crop instead of guessing on the whole photo.
    display_bbox: Optional["DisplayBBox"] = None
    # Optional four corners in original-image coordinates: TL, TR, BR, BL.
    display_quad: Optional[list[int]] = Field(default=None, min_length=8, max_length=8)
    expected_digits: Optional[int] = Field(default=None, ge=4, le=12)


class DisplayBBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class ConfidenceValue(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class QualityResult(BaseModel):
    state: str
    score: float
    width: int
    height: int
    source_width: int = 0
    source_height: int = 0
    low_resolution: bool = False


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
    preprocessing: list[str] = []
    stages: list[PipelineStage] = []
    auto_approval_eligible: bool = False
    error_message: Optional[str] = None
