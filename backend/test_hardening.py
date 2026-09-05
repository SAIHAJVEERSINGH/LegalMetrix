from app.hardening import (
    detect_cross_image_conflicts,
    harden_ai_result,
)
from app.schemas import AIResult, Product, Declaration


def declaration(field, value, confidence=0.9, evidence=None):
    return Declaration(
        field=field,
        value=value,
        confidence=confidence,
        evidence=evidence or [value],
    )


def base_ai(declarations):
    return AIResult(
        product=Product(
            name="Badam Shakers",
            brand="Amul",
            category="Milkshake",
        ),
        declarations=declarations,
        country_of_origin=None,
        label_type="retail",
        ambiguities=[],
    )


def test_duplicate_declarations_are_merged():
    ai = base_ai([
        declaration(
            "net_quantity",
            "200 mL",
            0.80,
            ["NET QTY 200 mL"],
        ),
        declaration(
            "net_quantity",
            "200 mL",
            0.95,
            ["Net Qty 200 mL"],
        ),
    ])

    ocr = """
    IMAGE 1
    NET QTY 200 mL
    """

    result = harden_ai_result(ai, ocr)

    quantity = [
        item
        for item in result.declarations
        if item.field == "net_quantity"
    ]

    assert len(quantity) == 1
    assert quantity[0].value == "200 mL"


def test_conflicting_declarations_create_review_ambiguity():
    ai = base_ai([
        declaration(
            "net_quantity",
            "200 mL",
            evidence=["NET QTY 200 mL"],
        ),
        declaration(
            "net_quantity",
            "250 mL",
            evidence=["NET QTY 250 mL"],
        ),
    ])

    ocr = """
    IMAGE 1
    NET QTY 200 mL

    IMAGE 2
    NET QTY 250 mL
    """

    result = harden_ai_result(ai, ocr)

    assert any(
        "Conflicting values detected" in item
        for item in result.ambiguities
    )


def test_cross_image_quantity_conflict():
    ocr = """
    IMAGE 1
    NET QTY 200 mL

    IMAGE 2
    NET QTY 250 mL
    """

    conflicts = detect_cross_image_conflicts(ocr)

    assert len(conflicts) >= 1
    assert "quantity" in conflicts[0].lower()


def test_cross_image_identical_quantity_is_safe():
    ocr = """
    IMAGE 1
    NET QTY 200 mL

    IMAGE 2
    NET QTY 200 mL
    """

    conflicts = detect_cross_image_conflicts(ocr)

    assert conflicts == []


def test_supported_evidence_is_safe():
    ai = base_ai([
        declaration(
            "consumer_care",
            "customercare@amul.coop",
            evidence=["customercare@amul.coop"],
        )
    ])

    ocr = """
    IMAGE 1
    customercare@amul.coop
    """

    result = harden_ai_result(ai, ocr)

    assert not any(
        "could not be matched" in item
        for item in result.ambiguities
    )


def test_unsupported_evidence_is_reviewable():
    ai = base_ai([
        declaration(
            "consumer_care",
            "customercare@amul.coop",
            evidence=["FAKE EVIDENCE"],
        )
    ])

    ocr = """
    IMAGE 1
    customercare@amul.coop
    """

    result = harden_ai_result(ai, ocr)

    assert any(
        "could not be matched" in item
        for item in result.ambiguities
    )


def test_valid_date_is_not_flagged():
    ai = base_ai([
        declaration(
            "manufacture_date",
            "17-MAY-26",
            evidence=["17-MAY-26"],
        )
    ])

    ocr = """
    IMAGE 1
    MFD 17-MAY-26
    """

    result = harden_ai_result(ai, ocr)

    assert not any(
        "structurally invalid" in item
        for item in result.ambiguities
    )


def test_invalid_date_is_flagged_for_review():
    ai = base_ai([
        declaration(
            "manufacture_date",
            "31-FEB-26",
            evidence=["31-FEB-26"],
        )
    ])

    ocr = """
    IMAGE 1
    MFD 31-FEB-26
    """

    result = harden_ai_result(ai, ocr)

    assert any(
        "structurally invalid" in item
        for item in result.ambiguities
    )


if __name__ == "__main__":
    test_duplicate_declarations_are_merged()
    test_conflicting_declarations_create_review_ambiguity()
    test_cross_image_quantity_conflict()
    test_cross_image_identical_quantity_is_safe()
    test_supported_evidence_is_safe()
    test_unsupported_evidence_is_reviewable()
    test_valid_date_is_not_flagged()
    test_invalid_date_is_flagged_for_review()

    print("HARDENING TESTS: PASS")
