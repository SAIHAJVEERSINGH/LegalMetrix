import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .schemas import AIResult, Product, Declaration

load_dotenv()


MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
API_KEY = os.getenv("GROQ_API_KEY")


SYSTEM_PROMPT = """
You are LegalMetrix, an expert packaged-commodity label analysis system.

You receive OCR text extracted from a product package.

Your job is NOT to decide legal compliance.

Your job is to intelligently interpret the OCR and extract factual label information.

Extract when present:

1. Product/common/generic name
2. Brand
3. Product category
4. Manufacturer name and address
5. Packer name and address
6. Importer name and address
7. Country of origin
8. Net quantity
9. MRP / retail sale price
10. Manufacturing/packing date
11. Best before / use by
12. Consumer care information
13. Unit sale price
14. Dimensions where applicable

Important:
- OCR may contain spelling errors.
- Do not invent missing information.
- If something is uncertain, mark the confidence lower.
- Evidence must contain short exact snippets from the OCR text.
- Preserve values such as Rs., ₹, g, kg, ml, L, cm, etc.
- Distinguish MRP from other prices.
- Distinguish manufacturing dates from expiry/best-before dates.
- Return only information supported by the OCR.

Return valid JSON matching the requested structure.
"""


def _empty_result() -> AIResult:
    return AIResult(
        product=Product(),
        declarations=[],
        country_of_origin=None,
        label_type=None,
        ambiguities=[],
    )


def process_ocr(ocr_text: str) -> AIResult:
    if not API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing from .env")

    if not ocr_text.strip():
        return _empty_result()

    client = OpenAI(
        api_key=API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    schema = {
        "type": "object",
        "properties": {
            "product": {
                "type": "object",
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "brand": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                },
                "required": ["name", "brand", "category"],
                "additionalProperties": False,
            },
            "declarations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "value": {"type": ["string", "null"]},
                        "confidence": {"type": "number"},
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "field",
                        "value",
                        "confidence",
                        "evidence",
                    ],
                    "additionalProperties": False,
                },
            },
            "country_of_origin": {"type": ["string", "null"]},
            "label_type": {"type": ["string", "null"]},
            "ambiguities": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "product",
            "declarations",
            "country_of_origin",
            "label_type",
            "ambiguities",
        ],
        "additionalProperties": False,
    }

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "OCR TEXT:\n\n"
                    + ocr_text
                    + "\n\nExtract the structured information."
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "label_extraction",
                "strict": True,
                "schema": schema,
            },
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("Groq returned an empty response")

    data: Any = json.loads(content)

    product_data = data.get("product") or {}
    declarations_data = data.get("declarations") or []

    if isinstance(declarations_data, dict):
        declarations_data = [
            {
                "field": key,
                "value": value,
                "confidence": 0.5,
                "evidence": [],
            }
            for key, value in declarations_data.items()
        ]

    return AIResult(
        product=Product(
            name=product_data.get("name"),
            brand=product_data.get("brand"),
            category=product_data.get("category"),
        ),
        declarations=[
            Declaration(
                field=item.get("field", ""),
                value=item.get("value"),
                confidence=float(item.get("confidence", 0)),
                evidence=item.get("evidence") or [],
            )
            for item in declarations_data
        ],
        country_of_origin=data.get("country_of_origin"),
        label_type=data.get("label_type"),
        ambiguities=data.get("ambiguities") or [],
    )
