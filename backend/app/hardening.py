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


NULL_LIKE_VALUES = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "not applicable",
    "not available",
    "not detected",
    "unknown",
}


def _clean_optional_value(value):
    """
    Convert model placeholders into actual missing values.
    """
    if value is None:
        return None

    text = str(value).strip()

    if text.lower() in NULL_LIKE_VALUES:
        return None

    return text


def _extract_consumer_care_from_ocr(ocr_text: str):
    """
    Deterministic OCR-backed consumer-care fallback.

    This does not invent contact information.
    It only creates a declaration when OCR contains a strong
    consumer-care/contact anchor and captures nearby OCR text.
    """
    if not ocr_text:
        return None

    patterns = [
        r"customer\s+care",
        r"consumer\s+care",
        r"consumer\s+complaints?",
        r"consumer\s+contact",
        r"customer\s+service",
        r"helpline",
        r"toll[\s-]*free",
        r"contact\s+us",
    ]

    for pattern in patterns:
        match = re.search(pattern, ocr_text, re.I)
        if not match:
            continue

        start = max(0, match.start() - 80)
        end = min(len(ocr_text), match.end() + 220)

        evidence = re.sub(
            r"\s+",
            " ",
            ocr_text[start:end]
        ).strip()

        if evidence:
            return Declaration(
                field="consumer_care",
                value=evidence,
                confidence=0.90,
                evidence=[evidence],
            )

    return None


def _unit_sale_price_is_structurally_valid(value: str) -> bool:
    """
    Validate common unit-sale-price forms without making a legal decision.
    """
    if not value:
        return False

    text = str(value).strip().lower()

    price_match = re.search(
        r"(?:₹|rs\.?|inr|rupees)?\s*"
        r"\d+(?:[.,]\d+)?",
        text,
        re.I,
    )

    if not price_match:
        return False

    unit_match = re.search(
        r"(?:/|per)\s*"
        r"(mg|g|kg|ml|l|cm|mm|m|number|no\.?|piece|pieces|unit|units)\b",
        text,
        re.I,
    )

    return bool(unit_match)


def _is_redundant_unit_price_ambiguity(message: str) -> bool:
    """
    AI sometimes reports a generic Unit Sale Price ambiguity even when
    the deterministic parser has already established a valid declaration.
    """
    text = _norm(message)
    return (
        "unit sale price" in text
        or "unit_sale_price" in text
    )


def _explicit_country_of_origin(ocr_text: str) -> bool:
    """
    Country of origin is accepted only when the OCR contains
    explicit origin wording.

    A manufacturer/importer address containing a country name
    is NOT sufficient evidence of country of origin.
    """
    if not ocr_text:
        return False

    patterns = [
        r"\bcountry\s+of\s+origin\b",
        r"\bmade\s+in\b",
        r"\bproduct\s+of\b",
        r"\bcountry\s*:\s*[a-z]",
        r"\borigin\s*:\s*[a-z]",
    ]

    return any(
        re.search(pattern, ocr_text, re.I)
        for pattern in patterns
    )


# ---------------------------------------------------------
# Evidence validation
# ---------------------------------------------------------

def _compact(text: str) -> str:
    """
    Remove formatting-only differences while preserving the
    actual alphanumeric evidence content.
    """
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _evidence_supported(evidence: str, ocr_text: str) -> bool:
    """
    Evidence must be supported by OCR.

    Matching tolerates harmless differences in:
      - case
      - whitespace
      - punctuation
      - separators such as ':' '/' '-'

    We still require the complete compact evidence string to
    occur in the compact OCR text.
    """
    if not evidence or not ocr_text:
        return False

    normalized_evidence = _norm(evidence)
    normalized_ocr = _norm(ocr_text)

    if normalized_evidence in normalized_ocr:
        return True

    compact_evidence = _compact(evidence)
    compact_ocr = _compact(ocr_text)

    return bool(compact_evidence) and compact_evidence in compact_ocr


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

    # Deterministic consumer-care fallback.
    # Only runs when Groq did not already provide the field.
    consumer_care_fields = {
        "consumer_care",
        "consumer_care_information",
        "customer_care",
        "consumer_complaint_contact",
        "consumer_contact",
    }

    if not any(field in grouped for field in consumer_care_fields):
        fallback_consumer_care = _extract_consumer_care_from_ocr(ocr_text)

        if fallback_consumer_care is not None:
            grouped.setdefault(
                "consumer_care",
                []
            ).append(fallback_consumer_care)

    merged: List[Declaration] = []
    ambiguities = list(ai.ambiguities or [])

    for field, declarations in grouped.items():
        values = [
            cleaned
            for item in declarations
            for cleaned in [_clean_optional_value(item.value)]
            if cleaned is not None
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

        valid_declarations = [
            item
            for item in declarations
            if _clean_optional_value(item.value) is not None
        ]

        if not valid_declarations:
            continue

        best = max(
            valid_declarations,
            key=lambda item: float(item.confidence or 0.0),
        )

        best_value = _clean_optional_value(best.value)

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
                value=best_value,
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

    # Country-of-origin inference protection.
    if ai.country_of_origin and not _explicit_country_of_origin(ocr_text):
        ambiguities.append(
            "Country of origin was returned by AI without an explicit "
            "origin declaration in the OCR; the inferred value was discarded."
        )
        country_of_origin = None
    else:
        country_of_origin = _clean_optional_value(ai.country_of_origin)

    # Clean top-level label type as well.
    label_type = _clean_optional_value(ai.label_type)

    # Cross-image consistency.
    ambiguities.extend(
        detect_cross_image_conflicts(ocr_text)
    )

    # Remove a generic AI unit-sale-price ambiguity only when
    # the deterministic declaration itself is structurally valid.
    unit_price_declaration = next(
        (
            item
            for item in merged
            if str(item.field or "").strip().lower()
            in {
                "unit_sale_price",
                "unit_price",
                "unit sale price",
                "sale_price_per_unit",
            }
        ),
        None,
    )

    if (
        unit_price_declaration is not None
        and _unit_sale_price_is_structurally_valid(
            unit_price_declaration.value
        )
    ):
        ambiguities = [
            item
            for item in ambiguities
            if not _is_redundant_unit_price_ambiguity(str(item))
        ]

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
        country_of_origin=country_of_origin,
        label_type=label_type,
        ambiguities=unique_ambiguities,
    )


