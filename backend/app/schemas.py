from pydantic import BaseModel, Field
from typing import List, Optional


class Product(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None


class Declaration(BaseModel):
    field: str
    value: Optional[str] = None
    confidence: float = 0.0
    evidence: List[str] = Field(default_factory=list)


class AIResult(BaseModel):
    product: Product
    declarations: List[Declaration] = Field(default_factory=list)
    country_of_origin: Optional[str] = None
    label_type: Optional[str] = None
    ambiguities: List[str] = Field(default_factory=list)


class ComplianceIssue(BaseModel):
    rule: str
    field: str
    status: str
    reason: str


class ComplianceResult(BaseModel):
    status: str
    score: int
    passed: int
    failed: int
    review: int
    issues: List[ComplianceIssue] = Field(default_factory=list)


class InspectionResponse(BaseModel):
    success: bool
    ocr_text: str
    ai: AIResult
    compliance: ComplianceResult
