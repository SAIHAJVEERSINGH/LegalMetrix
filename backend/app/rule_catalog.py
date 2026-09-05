"""
LegalMetrix regulatory rule catalog.

This catalog is intentionally limited to the Legal Metrology
(Packaged Commodities) Rules, 2011 screening areas that can
reasonably be represented by the current image/OCR pipeline.

The application is a screening aid, not an enforcement authority.
"""

RULES = {
    "RULE_4": {
        "reference": "Rule 4",
        "title": "Pre-packing and sale",
        "type": "applicability",
    },

    "RULE_5": {
        "reference": "Rule 5",
        "title": "Standard packages",
        "type": "commodity_specific",
    },

    "RULE_6_PRODUCT": {
        "reference": "Rule 6",
        "title": "Mandatory declarations",
        "type": "declaration",
    },

    "RULE_6_ORIGIN": {
        "reference": "Rule 6",
        "title": "Country of origin for imported products",
        "type": "conditional",
    },

    "RULE_6_QUANTITY": {
        "reference": "Rule 6",
        "title": "Net quantity declaration",
        "type": "declaration",
    },

    "RULE_6_PRICE": {
        "reference": "Rule 6",
        "title": "Retail sale price / MRP",
        "type": "declaration",
    },

    "RULE_6_CONSUMER": {
        "reference": "Rule 6",
        "title": "Consumer care information",
        "type": "declaration",
    },

    "RULE_6_DIMENSIONS": {
        "reference": "Rule 6",
        "title": "Dimensions where applicable",
        "type": "conditional",
    },

    "RULE_6_11": {
        "reference": "Rule 6(11)",
        "title": "Unit sale price",
        "type": "declaration",
    },

    "RULE_7": {
        "reference": "Rule 7",
        "title": "Principal display panel",
        "type": "physical_verification",
    },

    "RULE_8": {
        "reference": "Rule 8",
        "title": "Place of declarations",
        "type": "visual_screening",
    },

    "RULE_9": {
        "reference": "Rule 9",
        "title": "Manner of declaration",
        "type": "visual_screening",
    },

    "RULE_10": {
        "reference": "Rule 10",
        "title": "Manufacturer / packer / importer details",
        "type": "declaration",
    },

    "RULE_11": {
        "reference": "Rule 11",
        "title": "General quantity provisions",
        "type": "physical_verification",
    },

    "RULE_12": {
        "reference": "Rule 12",
        "title": "Manner of quantity declaration",
        "type": "declaration",
    },

    "RULE_13": {
        "reference": "Rule 13",
        "title": "Specific package declarations",
        "type": "conditional",
    },

    "RULE_14": {
        "reference": "Rule 14",
        "title": "Dimensions of specified commodities",
        "type": "commodity_specific",
    },

    "RULE_15": {
        "reference": "Rule 15",
        "title": "Dimensions / weight related to price",
        "type": "commodity_specific",
    },

    "RULE_16": {
        "reference": "Rule 16",
        "title": "Number of usable sheets",
        "type": "commodity_specific",
    },

    "RULE_17": {
        "reference": "Rule 17",
        "title": "Container-type commodities",
        "type": "commodity_specific",
    },

    "RULE_18": {
        "reference": "Rule 18",
        "title": "Retail / wholesale dealer requirements",
        "type": "transactional",
    },

    "RULE_22": {
        "reference": "Rule 22",
        "title": "Maximum permissible error",
        "type": "physical_verification",
    },

    "RULE_23": {
        "reference": "Rule 23",
        "title": "Deceptive packages",
        "type": "visual_physical_screening",
    },

    "RULE_24": {
        "reference": "Rule 24",
        "title": "Wholesale package declarations",
        "type": "conditional",
    },

    "RULE_25": {
        "reference": "Rule 25",
        "title": "Export packages",
        "type": "conditional",
    },

    "RULE_26": {
        "reference": "Rule 26",
        "title": "Exemptions",
        "type": "applicability",
    },

    "RULE_27": {
        "reference": "Rule 27",
        "title": "Registration of manufacturers / packers / importers",
        "type": "external_verification",
    },

    "RULE_28": {
        "reference": "Rule 28",
        "title": "Shorter address",
        "type": "external_verification",
    },

    "RULE_29": {
        "reference": "Rule 29",
        "title": "Registration records",
        "type": "external_verification",
    },

    "RULE_30": {
        "reference": "Rule 30",
        "title": "Registered manufacturer / packer lists",
        "type": "external_verification",
    },

    "RULE_31": {
        "reference": "Rule 31",
        "title": "Advertisements",
        "type": "transactional",
    },

    "RULE_32": {
        "reference": "Rule 32",
        "title": "Fine",
        "type": "enforcement",
    },

    "RULE_32A": {
        "reference": "Rule 32A",
        "title": "Compounding",
        "type": "enforcement",
    },

    "AMENDMENT_2025_PAN_MASALA": {
        "reference": "Rule 26 amendment",
        "title": "Pan masala exemption change",
        "type": "applicability",
        "effective": "2026-02-01",
    },

    "AMENDMENT_2026_ECOMMERCE": {
        "reference": "Rule 6(10A)",
        "title": "Imported product e-commerce country-of-origin filter",
        "type": "ecommerce",
        "effective": "2027-07-01",
    },
}


def get_rule(rule_id: str):
    return RULES.get(rule_id)


def all_rules():
    return RULES.copy()
