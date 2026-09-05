import re
from datetime import datetime
from typing import Dict, List, Tuple

from .schemas import AIResult, Declaration


# ---------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _norm_value(text: str) -> str:
    value = _norm(text)

    # Normalize common OCR/unit variations.
    value = value.replace("liters", "l")
    value = value.replace("litres", "l")
    value = value.replace("liter", "l")
    value = value.replace("litre", "l")
    value = value.replace("milliliters", "ml")
    value = value.replace("millilitres", "ml")
    value = value.replace("grams", "g")
    value = value.replace("kilograms", "kg")

    return value


# ---------------------------------------------------------
# Evidence validation
# ---------------------------------------------------------

def _evidence_supported(evidence: str, ocr_text: str) -> bool:
    """
    Evidence must actually occur in the OCR text.

    We use normalized whitespace/case so harmless OCR spacing
    differences do not create false reviews.
    """
    if not evidence or not ocr_text:
        return False

    return _norm(evidence) in _norm(ocr_text)


# ---------------------------------------------------------
# Date validation
# ---------------------------------------------------------

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
    re.compile(
        r"\b\d{1,2}[-\s](?:jan|feb|mar|apr|may|jun|jul|aug|sep|"
        r"oct|nov|dec)[-\s]\d{2,4}\b",
        re.I,
    ),
    re.compile(
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"[-\s]\d{2,4}\b",
        re.I,
    ),
    re.compile(r"\b\d{1,2}[-/]\d{1,2}\b"),
]


def _looks_like_date_expression(value: str) -> bool:
    text = _norm(value)

    return any(
        pattern.search(text)
        for pattern in DATE_PATTERNS
    )


def _date_is_structurally_valid(value: str) -> bool:
    """
    Conservative validation.

    We only reject an explicit date-like expression when its
    calendar components are clearly impossible.

    Expressions such as '12 months from MFD' are left alone.
    """
    text = _norm(value)

    match = re.search(
        r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b",
        text,
    )

    if match:
        day, month, year = map(int, match.groups())

        if year < 100:
            year += 2000

        try:
            datetime(year, month, day)
            return True
        except ValueError:
            return False

    match = re.search(
        r"\b(\d{1,2})[-\s]"
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"[-\s](\d{2,4})\b",
        text,
        re.I,
    )

    if match:
        day = int(match.group(1))
        month_text = match.group(2).lower()
        year = int(match.group(3))

        months = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }

        if year < 100:
            year += 2000

        try:
            datetime(year, months[month_text], day)
            return True
        except ValueError:
            return False

    # Month/year and day/month expressions are structurally acceptable.
    return True


# ---------------------------------------------------------
# Cross-image OCR consistency
# ---------------------------------------------------------

def _image_blocks(ocr_text: str) -> Dict[int, str]:
    """
    Split combined OCR into IMAGE 1, IMAGE 2, ... blocks.
    """
    matches = list(
        re.finditer(
            r"(?im)^\s*IMAGE\s+(\d+)\s*$",
            ocr_text,
        )
    )

    blocks: Dict[int, str] = {}

    for index, match in enumerate(matches):
        image_number = int(match.group(1))
        start = match.end()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(ocr_text)
        )

        blocks[image_number] = ocr_text[start:end].strip()

    return blocks


def _extract_quantities(text: str) -> List[str]:
    pattern = re.compile(
        r"\b\d+(?:[.,]\d+)?\s*"
        r"(?:mg|g|kg|ml|l|litre|liter|litres|liters)\b",
        re.I,
    )

    return [
        _norm_value(match.group(0))
        for match in pattern.finditer(text)
    ]


def _extract_dates(text: str) -> List[str]:
    results = []

    for pattern in DATE_PATTERNS[:3]:
        results.extend(
            _norm_value(match.group(0))
            for match in pattern.finditer(text)
        )

    return list(dict.fromkeys(results))


def detect_cross_image_conflicts(ocr_text: str) -> List[str]:
    """
    Detect only strong conflicts.

    Repeated identical declarations across package sides are fine.
    Different detected net quantities or dates trigger REVIEW.
    """
    blocks = _image_blocks(ocr_text)

    if len(blocks) < 2:
        return []

    conflicts = []

    quantity_by_image: Dict[int, List[str]] = {}
    date_by_image: Dict[int, List[str]] = {}

    for image_number, text in blocks.items():
        quantities = list(dict.fromkeys(_extract_quantities(text)))
        dates = _extract_dates(text)

        if quantities:
            quantity_by_image[image_number] = quantities

        if dates:
            date_by_image[image_number] = dates

    all_quantities = {
        value
        for values in quantity_by_image.values()
        for value in values
    }

    if len(all_quantities) > 1:
        details = "; ".join(
            f"Image {image}: {', '.join(values)}"
            for image, values in sorted(quantity_by_image.items())
        )

        conflicts.append(
            "Conflicting net-quantity declarations were detected "
            f"across package images ({details})."
        )

    all_dates = {
        value
        for values in date_by_image.values()
        for value in values
    }

    # Do not treat multiple legitimate dates on one package as a conflict.
    # Only flag when different images provide incompatible date evidence.
    if len(date_by_image) >= 2 and len(all_dates) > 1:
        details = "; ".join(
            f"Image {image}: {', '.join(values)}"
            for image, values in sorted(date_by_image.items())
        )

        conflicts.append(
            "Different date declarations were detected across "
            f"package images ({details}). Manual verification is required."
        )

    return conflicts


# ---------------------------------------------------------
# Declaration consolidation + validation
# ---------------------------------------------------------

def harden_ai_result(
    ai: AIResult,
    ocr_text: str,
) -> AIResult:
    """
    Deterministic post-processing after Groq.

    This never creates a new compliance PASS/FAIL.
    It only:
      - consolidates duplicate fields,
      - preserves evidence,
      - detects conflicting values,
      - validates evidence support,
      - validates explicit date expressions.
    """
    grouped: Dict[str, List[Declaration]] = {}

    for declaration in ai.declarations:
        field = str(declaration.field or "").strip().lower()

        if not field:
            continue

        grouped.setdefault(field, []).append(declaration)

    merged: List[Declaration] = []
    ambiguities = list(ai.ambiguities or [])

    for field, declarations in grouped.items():
        values = [
            str(item.value).strip()
            for item in declarations
            if item.value is not None and str(item.value).strip()
        ]

        normalized_values = {
            _norm_value(value)
            for value in values
        }

        # Strong conflicting declaration detection.
        if len(normalized_values) > 1:
            ambiguities.append(
                f"Conflicting values detected for '{field}': "
                + " | ".join(values)
            )

        best = max(
            declarations,
            key=lambda item: float(item.confidence or 0.0),
        )

        evidence: List[str] = []

        for item in declarations:
            for snippet in item.evidence or []:
                snippet = str(snippet).strip()

                if snippet and snippet not in evidence:
                    evidence.append(snippet)

        confidence = max(
            float(item.confidence or 0.0)
            for item in declarations
        )

        merged.append(
            Declaration(
                field=field,
                value=best.value,
                confidence=confidence,
                evidence=evidence,
            )
        )

        # Evidence must actually be supported by OCR.
        unsupported = [
            snippet
            for snippet in evidence
            if not _evidence_supported(snippet, ocr_text)
        ]

        if unsupported:
            ambiguities.append(
                f"Evidence for '{field}' could not be matched "
                "exactly to the OCR text."
            )

        # Conservative date validation.
        if field in {
            "manufacture_date",
            "manufacturing_date",
            "packing_date",
            "pack_date",
            "date_of_manufacture",
            "date_of_packing",
            "best_before",
            "best_before_use_by",
            "use_by",
        } and best.value:
            if _looks_like_date_expression(best.value):
                if not _date_is_structurally_valid(best.value):
                    ambiguities.append(
                        f"Date value for '{field}' appears structurally invalid: "
                        f"{best.value}"
                    )

    # Cross-image consistency.
    ambiguities.extend(
        detect_cross_image_conflicts(ocr_text)
    )

    # Deduplicate ambiguity messages while preserving order.
    unique_ambiguities = list(
        dict.fromkeys(
            str(item).strip()
            for item in ambiguities
            if str(item).strip()
        )
    )

    return AIResult(
        product=ai.product,
        declarations=merged,
        country_of_origin=ai.country_of_origin,
        label_type=ai.label_type,
        ambiguities=unique_ambiguities,
    )
