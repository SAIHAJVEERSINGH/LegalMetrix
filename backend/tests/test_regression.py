import unittest

from app.schemas import (
    AIResult,
    Product,
    Declaration,
)

from app.compliance import run_compliance


class LegalMetrixRegressionTests(unittest.TestCase):

    def make_ai(self, declarations=None, product_name="Test Product"):
        return AIResult(
            product=Product(
                name=product_name,
                brand="Test Brand",
                category="Food",
            ),
            declarations=declarations or [],
            country_of_origin="India",
            label_type="retail package",
            ambiguities=[],
        )

    def declaration(self, field, value):
        return Declaration(
            field=field,
            value=value,
            confidence=0.99,
            evidence=[value],
        )

    def test_compliance_engine_runs(self):

        ai = self.make_ai([
            self.declaration(
                "manufacturer",
                "ABC Foods Pvt Ltd, Jaipur",
            ),
            self.declaration(
                "net_quantity",
                "500 g",
            ),
            self.declaration(
                "mrp",
                "₹120",
            ),
            self.declaration(
                "manufacture_date",
                "08/2026",
            ),
            self.declaration(
                "consumer_care",
                "1800-123-4567",
            ),
            self.declaration(
                "best_before",
                "6 months from manufacture",
            ),
            self.declaration(
                "unit_sale_price",
                "₹0.24/g",
            ),
        ])

        result = run_compliance(ai)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.passed, 0)
        self.assertGreaterEqual(result.failed, 0)
        self.assertGreaterEqual(result.review, 0)

        self.assertEqual(
            result.passed + result.failed + result.review,
            len(result.issues),
        )

    def test_missing_mrp_is_detected(self):

        ai = self.make_ai([
            self.declaration(
                "manufacturer",
                "ABC Foods Pvt Ltd",
            ),
            self.declaration(
                "net_quantity",
                "500 g",
            ),
            self.declaration(
                "manufacture_date",
                "08/2026",
            ),
            self.declaration(
                "consumer_care",
                "1800-123-4567",
            ),
        ])

        result = run_compliance(ai)

        mrp_issues = [
            issue
            for issue in result.issues
            if issue.field == "mrp"
        ]

        self.assertEqual(len(mrp_issues), 1)
        self.assertEqual(mrp_issues[0].status, "FAIL")

    def test_invalid_quantity_goes_to_review(self):

        ai = self.make_ai([
            self.declaration(
                "manufacturer",
                "ABC Foods Pvt Ltd",
            ),
            self.declaration(
                "net_quantity",
                "five hundred",
            ),
            self.declaration(
                "mrp",
                "₹120",
            ),
            self.declaration(
                "manufacture_date",
                "08/2026",
            ),
            self.declaration(
                "consumer_care",
                "1800-123-4567",
            ),
        ])

        result = run_compliance(ai)

        quantity_issues = [
            issue
            for issue in result.issues
            if issue.field == "net_quantity"
        ]

        self.assertEqual(len(quantity_issues), 1)
        self.assertEqual(quantity_issues[0].status, "REVIEW")

    def test_price_detector_handles_rupee_symbol(self):

        ai = self.make_ai([
            self.declaration(
                "manufacturer",
                "ABC Foods Pvt Ltd",
            ),
            self.declaration(
                "net_quantity",
                "500 g",
            ),
            self.declaration(
                "mrp",
                "₹120",
            ),
            self.declaration(
                "manufacture_date",
                "08/2026",
            ),
            self.declaration(
                "consumer_care",
                "1800-123-4567",
            ),
        ])

        result = run_compliance(ai)

        mrp_issues = [
            issue
            for issue in result.issues
            if issue.field == "mrp"
        ]

        self.assertEqual(len(mrp_issues), 1)
        self.assertEqual(mrp_issues[0].status, "PASS")


if __name__ == "__main__":
    unittest.main()
