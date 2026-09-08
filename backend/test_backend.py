from decimal import Decimal

from app.compliance import (
    looks_like_price,
    looks_like_quantity,
    parse_quantity,
    parse_unit_price,
    expected_unit_for_quantity,
    run_compliance,
)
from app.schemas import AIResult, Product, Declaration


def declaration(field, value):
    return Declaration(
        field=field,
        value=value,
        confidence=1.0,
        evidence=[value],
    )


def complete_domestic():
    return AIResult(
        product=Product(
            name="Milkshake",
            brand="Test Brand",
            category="Milkshake",
        ),
        declarations=[
            declaration("manufacturer", "Test Foods Ltd., Jaipur"),
            declaration("net_quantity", "200 ml"),
            declaration("mrp", "₹40"),
            declaration("manufacture_date", "17-MAY-26"),
            declaration("consumer_care", "care@example.com"),
            declaration("best_before", "17-MAY-27"),
            declaration("unit_sale_price", "₹0.20/ml"),
        ],
        country_of_origin=None,
        label_type="retail",
        ambiguities=[],
    )


def test_quantity():
    assert looks_like_quantity("200 ml")
    assert looks_like_quantity("1 kg")
    assert parse_quantity("200 ml") == (Decimal("200"), "ml")


def test_price():
    assert looks_like_price("₹40")
    assert looks_like_price("299.00")


def test_unit_price():
    result = parse_unit_price("₹0.20/ml")

    assert result is not None
    price, unit = result

    assert price == Decimal("0.20")
    assert unit == "ml"
    assert expected_unit_for_quantity("200 ml") == "ml"
    assert parse_unit_price("₹1.50 per g") == (Decimal("1.50"), "g")
    assert parse_unit_price("₹2.00/kg") == (Decimal("2.00"), "kg")


def test_category_ambiguity():
    ai = complete_domestic()
    ai.ambiguities = ["category"]

    result = run_compliance(ai)

    assert not any(
        issue.field == "ambiguous_information"
        for issue in result.issues
    )


def test_domestic_origin_not_required():
    ai = complete_domestic()

    result = run_compliance(ai)

    assert not any(
        issue.field == "country_of_origin"
        and issue.status == "REVIEW"
        for issue in result.issues
    )


def test_imported_missing_origin_is_review():
    ai = complete_domestic()

    ai.declarations.append(
        declaration(
            "importer",
            "Imported Foods Pvt Ltd.",
        )
    )

    ai.country_of_origin = None

    result = run_compliance(ai)

    assert any(
        issue.field == "country_of_origin"
        and issue.status == "REVIEW"
        for issue in result.issues
    )


def test_complete_pipeline_does_not_fail():
    ai = complete_domestic()

    result = run_compliance(ai)

    assert result.failed == 0
    assert result.passed >= 7
    assert result.review >= 1


if __name__ == "__main__":
    test_quantity()
    test_price()
    test_unit_price()
    test_category_ambiguity()
    test_domestic_origin_not_required()
    test_imported_missing_origin_is_review()
    test_complete_pipeline_does_not_fail()

    print("ALL REGRESSION TESTS: PASS")

