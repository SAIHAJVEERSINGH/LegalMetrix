import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from .applicability import (
    best_before_is_applicable,
    determine_context,
    dimensions_are_applicable,
    origin_is_applicable,
)
from .schemas import AIResult, ComplianceIssue, ComplianceResult


def declarations_map(ai: AIResult):
    result = {}

    for declaration in ai.declarations:
        field = str(declaration.field or "").strip().lower()

        if field:
            result[field] = declaration

    return result


def find_field(data, *names):
    for name in names:
        key = name.strip().lower()

        if key in data:
            return data[key]

    return None


def looks_like_price(value: str) -> bool:
    """
    Validate a price value conservatively.

    MRP is already identified by the AI extraction field, so the
    validator must not require a currency symbol to be present.
    OCR commonly extracts:
        ₹299
        Rs. 299
        INR 299
        MRP 299
        299.00

    The field context remains important: this validator is used
    for the extracted MRP field, not arbitrary OCR text.
    """

    if value is None:
        return False

    text = str(value).strip().lower()

    if not text:
        return False

    # Remove common price labels/currency markers.
    cleaned = re.sub(
        r"\b(?:mrp|max(?:imum)?\s+retail\s+price|rs\.?|inr|rupees)\b",
        " ",
        text,
        flags=re.I,
    )

    cleaned = cleaned.replace("₹", " ")

    # A price must contain a numeric value.
    match = re.search(r"(?<![\d.])\d+(?:[.,]\d{1,2})?(?![\d.])", cleaned)

    if not match:
        return False

    try:
        amount = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return False

    return amount >= Decimal("0")


def parse_quantity(value: str) -> Optional[Tuple[Decimal, str]]:
    if value is None:
        return None

    text = str(value).strip().lower()

    pattern = re.search(
        r"(\d+(?:\.\d+)?)\s*(mg|g|kg|ml|l|litre|liter|litres|liters|"
        r"cm|mm|m|pcs?|pieces?|units?|numbers?)\b",
        text,
    )

    if not pattern:
        return None

    try:
        number = Decimal(pattern.group(1))
    except InvalidOperation:
        return None

    unit = pattern.group(2)

    aliases = {
        "litre": "l",
        "liter": "l",
        "litres": "l",
        "liters": "l",
        "pieces": "number",
        "piece": "number",
        "pcs": "number",
        "pc": "number",
        "units": "number",
        "unit": "number",
        "numbers": "number",
        "mg": "mg",
        "g": "g",
        "kg": "kg",
        "ml": "ml",
        "l": "l",
        "cm": "cm",
        "mm": "mm",
        "m": "m",
    }

    return number, aliases.get(unit, unit)


def looks_like_quantity(value: str) -> bool:
    return parse_quantity(value) is not None


def parse_price(value: str) -> Optional[Decimal]:
    if value is None:
        return None

    text = str(value).strip().lower()

    cleaned = re.sub(r"[₹]|rs\.?|inr|rupees", " ", text)

    match = re.search(r"\d+(?:\.\d+)?", cleaned)

    if not match:
        return None

    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def parse_unit_price(value: str) -> Optional[Tuple[Decimal, str]]:
    if value is None:
        return None

    text = str(value).strip().lower()

    price = parse_price(text)

    if price is None:
        return None

    unit_match = re.search(
        r"(?:/|per)\s*"
        r"(mg|g|kg|ml|l|cm|mm|m|number|no\.?|piece|pieces|unit|units)\b",
        text,
    )

    if not unit_match:
        return None

    unit = unit_match.group(1)

    aliases = {
        "no.": "number",
        "piece": "number",
        "pieces": "number",
        "unit": "number",
        "units": "number",
    }

    return price, aliases.get(unit, unit)


def expected_unit_for_quantity(
    quantity_value: str,
) -> Optional[str]:
    parsed = parse_quantity(quantity_value)

    if parsed is None:
        return None

    amount, unit = parsed

    if unit == "mg":
        return "g"

    if unit == "g":
        return "g" if amount < Decimal("1000") else "kg"

    if unit == "kg":
        return "kg"

    if unit == "ml":
        return "ml" if amount < Decimal("1000") else "l"

    if unit == "l":
        return "l"

    if unit == "mm":
        return "cm"

    if unit == "cm":
        return "cm" if amount < Decimal("100") else "m"

    if unit == "m":
        return "m"

    if unit == "number":
        return "number"

    return None


def add_issue(
    issues,
    rule,
    field,
    status,
    reason,
):
    issues.append(
        ComplianceIssue(
            rule=rule,
            field=field,
            status=status,
            reason=reason,
        )
    )


def run_compliance(ai: AIResult) -> ComplianceResult:
    fields = declarations_map(ai)
    context = determine_context(ai)

    issues = []
    passed = 0
    failed = 0
    review = 0

    def check(
        rule: str,
        field: str,
        value,
        reason_if_missing: str,
        validator=None,
    ):
        nonlocal passed, failed, review

        if value is None or not value.value:
            add_issue(
                issues,
                rule,
                field,
                "FAIL",
                reason_if_missing,
            )
            failed += 1
            return

        if validator is not None:
            try:
                valid = validator(value.value)
            except Exception:
                valid = False

            if not valid:
                add_issue(
                    issues,
                    rule,
                    field,
                    "REVIEW",
                    (
                        "A value was detected, but its format "
                        "could not be confidently validated: "
                        f"{value.value}"
                    ),
                )
                review += 1
                return

        add_issue(
            issues,
            rule,
            field,
            "PASS",
            f"Detected: {value.value}",
        )
        passed += 1

    # -----------------------------------------------------
    # Rule 6 — common / generic product name
    # -----------------------------------------------------

    if ai.product.name:
        add_issue(
            issues,
            "Rule 6",
            "product_name",
            "PASS",
            (
                "Product/common/generic name detected: "
                f"{ai.product.name}"
            ),
        )
        passed += 1
    else:
        add_issue(
            issues,
            "Rule 6",
            "product_name",
            "FAIL",
            (
                "Product/common/generic name was not "
                "confidently detected."
            ),
        )
        failed += 1

    # -----------------------------------------------------
    # Rule 6 / Rule 10 — manufacturer / packer / importer
    # -----------------------------------------------------

    manufacturer = find_field(
        fields,
        "manufacturer",
        "manufacturer_name",
        "manufacturer_address",
    )

    packer = find_field(
        fields,
        "packer",
        "packer_name",
        "packer_address",
    )

    importer = find_field(
        fields,
        "importer",
        "importer_name",
        "importer_address",
    )

    responsible_party = manufacturer or packer or importer

    check(
        "Rule 6 / Rule 10",
        "manufacturer_packer_importer",
        responsible_party,
        (
            "Manufacturer, packer or importer name/address "
            "was not confidently detected."
        ),
    )

    # -----------------------------------------------------
    # Rule 6 / Rule 12 — net quantity
    # -----------------------------------------------------

    quantity = find_field(
        fields,
        "net_quantity",
        "quantity",
        "net_weight",
        "net_volume",
        "net_content",
    )

    check(
        "Rule 6 / Rule 12",
        "net_quantity",
        quantity,
        "Net quantity declaration was not confidently detected.",
        looks_like_quantity,
    )

    # -----------------------------------------------------
    # Rule 6 — MRP
    # -----------------------------------------------------

    mrp = find_field(
        fields,
        "mrp",
        "maximum_retail_price",
        "retail_sale_price",
        "maximum_retail_sale_price",
    )

    check(
        "Rule 6",
        "mrp",
        mrp,
        (
            "Maximum Retail Price / retail sale price "
            "was not confidently detected."
        ),
        looks_like_price,
    )

    # -----------------------------------------------------
    # Rule 6 — manufacture / packing date
    # -----------------------------------------------------

    manufacture_date = find_field(
        fields,
        "manufacture_date",
        "manufacturing_date",
        "packing_date",
        "pack_date",
        "date_of_manufacture",
        "date_of_packing",
    )

    check(
        "Rule 6",
        "manufacture_date",
        manufacture_date,
        (
            "Manufacturing/packing date was not "
            "confidently detected."
        ),
    )

    # -----------------------------------------------------
    # Rule 6 — consumer care
    # -----------------------------------------------------

    consumer_care = find_field(
        fields,
        "consumer_care",
        "consumer_care_information",
        "customer_care",
        "consumer_complaint_contact",
        "consumer_contact",
    )

    check(
        "Rule 6",
        "consumer_care",
        consumer_care,
        (
            "Consumer-care information was not "
            "confidently detected."
        ),
    )

    # -----------------------------------------------------
    # Rule 6 — country of origin
    #
    # Only applicable to imported products.
    # -----------------------------------------------------

    if origin_is_applicable(context):
        if ai.country_of_origin:
            add_issue(
                issues,
                "Rule 6",
                "country_of_origin",
                "PASS",
                (
                    "Country of origin detected for an "
                    f"apparently imported product: "
                    f"{ai.country_of_origin}"
                ),
            )
            passed += 1
        else:
            add_issue(
                issues,
                "Rule 6",
                "country_of_origin",
                "REVIEW",
                (
                    "The product appears to be imported, "
                    "but country of origin was not confidently "
                    "detected."
                ),
            )
            review += 1

    # -----------------------------------------------------
    # Rule 6 — best before / use by
    #
    # Food is treated as the strongest current applicability
    # signal. We do not fail every non-food commodity for
    # missing best-before information.
    # -----------------------------------------------------

    best_before = find_field(
        fields,
        "best_before",
        "best_before_date",
        "use_by",
        "use_by_date",
        "expiry",
        "expiry_date",
    )

    if best_before:
        add_issue(
            issues,
            "Rule 6",
            "best_before_use_by",
            "PASS",
            f"Detected: {best_before.value}",
        )
        passed += 1
    elif best_before_is_applicable(context):
        add_issue(
            issues,
            "Rule 6",
            "best_before_use_by",
            "REVIEW",
            (
                "The product appears to be a food commodity, "
                "but best-before/use-by information was not "
                "detected."
            ),
        )
        review += 1

    # -----------------------------------------------------
    # Rule 6(11) — unit sale price
    # -----------------------------------------------------

    unit_price = find_field(
        fields,
        "unit_sale_price",
        "unit_price",
        "unit sale price",
        "sale_price_per_unit",
    )

    if unit_price:
        parsed_unit_price = parse_unit_price(unit_price.value)

        if parsed_unit_price is None:
            add_issue(
                issues,
                "Rule 6(11)",
                "unit_sale_price",
                "REVIEW",
                (
                    "Unit sale price was detected, but its "
                    "price-per-unit format could not be "
                    f"confidently parsed: {unit_price.value}"
                ),
            )
            review += 1
        else:
            detected_price, detected_unit = parsed_unit_price
            expected_unit = (
                expected_unit_for_quantity(quantity.value)
                if quantity
                else None
            )

            if expected_unit and detected_unit != expected_unit:
                add_issue(
                    issues,
                    "Rule 6(11)",
                    "unit_sale_price",
                    "REVIEW",
                    (
                        f"Detected unit sale price: {unit_price.value}. "
                        f"Quantity suggests the applicable comparison "
                        f"unit is {expected_unit}."
                    ),
                )
                review += 1
            else:
                add_issue(
                    issues,
                    "Rule 6(11)",
                    "unit_sale_price",
                    "PASS",
                    (
                        "Unit sale price detected: "
                        f"{unit_price.value}"
                    ),
                )
                passed += 1
    else:
        add_issue(
            issues,
            "Rule 6(11)",
            "unit_sale_price",
            "REVIEW",
            (
                "Unit sale price was not detected. "
                "Applicability depends on the commodity, "
                "quantity and package."
            ),
        )
        review += 1

    # -----------------------------------------------------
    # Conditional dimensions
    #
    # Do not invent a failure from a photograph. If the
    # commodity appears dimension-sensitive and no dimensions
    # are detected, request verification.
    # -----------------------------------------------------

    if dimensions_are_applicable(context):
        dimensions = find_field(
            fields,
            "dimensions",
            "dimension",
            "length",
            "width",
            "height",
            "depth",
            "size",
        )

        if dimensions:
            add_issue(
                issues,
                "Rule 6 / Rule 14-17",
                "dimensions",
                "PASS",
                f"Dimension information detected: {dimensions.value}",
            )
            passed += 1
        else:
            add_issue(
                issues,
                "Rule 6 / Rule 14-17",
                "dimensions",
                "REVIEW",
                (
                    "The commodity may require dimensional "
                    "declarations, but no dimensional declaration "
                    "was confidently detected."
                ),
            )
            review += 1

    # -----------------------------------------------------
    # Rule 5 / Rule 26 applicability marker
    #
    # We do NOT invent a standard-pack failure without a
    # verified Second Schedule commodity mapping.
    # -----------------------------------------------------

    if context.pan_masala:
        add_issue(
            issues,
            "Rule 26",
            "pan_masala",
            "REVIEW",
            (
                "Pan masala detected. The 2025 amendment changed "
                "the Rule 26 treatment effective 1 February 2026; "
                "commodity-specific standard-pack applicability "
                "should be verified against the current Schedule."
            ),
        )
        review += 1

    # -----------------------------------------------------
    # Physical verification boundary
    #
    # These are deliberately REVIEW items only when the
    # current inspection contains information that suggests
    # the check matters. They prevent the system from making
    # false legal claims.
    # -----------------------------------------------------

    if quantity:
        quantity_value = quantity.value

        add_issue(
            issues,
            "Rule 11 / Rule 22",
            "physical_verification",
            "INFO",
            (
                f"Declared net quantity {quantity_value} was "
                "successfully detected from the label. "
                "This image-based inspection cannot verify the "
                "actual physical quantity inside the package or "
                "the applicable maximum permissible error. "
                "Physical measurement is required for definitive "
                "Rule 11 / Rule 22 verification."
            ),
        )


    # -----------------------------------------------------
    # AI ambiguities
    #
    # Category ambiguity is informational.
    # Country-of-origin ambiguity is handled by applicability.
    # Product-name ambiguity is reconciled conservatively.
    # -----------------------------------------------------

    for ambiguity in ai.ambiguities:
        if not ambiguity:
            continue

        ambiguity_text = str(ambiguity).strip().lower()

        if ambiguity_text == "category":
            continue

        if (
            "country_of_origin" in ambiguity_text
            or "country of origin" in ambiguity_text
            or ambiguity_text == "origin"
        ):
            if not origin_is_applicable(context):
                continue

        # -------------------------------------------------
        # Product-name reconciliation
        #
        # Example:
        #
        #   Almonds (100%)
        #   100% Natural Californian Almonds
        #
        # These describe the same underlying commodity.
        #
        # A genuine conflict such as:
        #
        #   Almonds
        #   Cashews
        #
        # remains REVIEW.
        # -------------------------------------------------

        if "product name" in ambiguity_text:
            candidates = re.findall(
                r"""['"]([^'"]+)['"]""",
                str(ambiguity),
            )

            if len(candidates) >= 2:
                ignored_words = {
                    "natural",
                    "pure",
                    "premium",
                    "fresh",
                    "original",
                    "authentic",
                    "quality",
                    "best",
                    "select",
                    "selected",
                    "californian",
                    "california",
                }

                normalized = []

                for candidate in candidates[:2]:
                    name = str(candidate).lower()

                    # Remove percentages such as 100%.
                    name = re.sub(
                        r"\d+(?:\.\d+)?\s*%",
                        " ",
                        name,
                    )

                    # Remove punctuation.
                    name = re.sub(
                        r"[^a-z0-9\s]",
                        " ",
                        name,
                    )

                    tokens = {
                        token
                        for token in name.split()
                        if token
                        and len(token) > 1
                        and token not in ignored_words
                        and not token.isdigit()
                    }

                    normalized.append(tokens)

                first_tokens = normalized[0]
                second_tokens = normalized[1]

                compatible = (
                    bool(first_tokens)
                    and bool(second_tokens)
                    and (
                        first_tokens.issubset(second_tokens)
                        or second_tokens.issubset(first_tokens)
                    )
                )

                if compatible:
                    continue

        add_issue(
            issues,
            "AI REVIEW",
            "ambiguous_information",
            "REVIEW",
            str(ambiguity),
        )
        review += 1

    # -----------------------------------------------------

# Final result
    # -----------------------------------------------------

    total = passed + failed + review

    if failed > 0:
        status = "NON_COMPLIANT"
    elif review > 0:
        status = "REVIEW"
    else:
        status = "COMPLIANT"

    score = round((passed / total) * 100) if total else 0

    return ComplianceResult(
        status=status,
        score=score,
        passed=passed,
        failed=failed,
        review=review,
        issues=issues,
    )


