import re
from dataclasses import dataclass
from typing import Optional

from .schemas import AIResult


@dataclass
class PackageContext:
    imported: bool = False
    food: bool = False
    textile: bool = False
    sheets: bool = False
    container: bool = False
    wholesale: bool = False
    advertisement: bool = False
    pan_masala: bool = False
    dimensions_relevant: bool = False
    physical_verification_required: bool = False


def _all_text(ai: AIResult) -> str:
    parts = [
        ai.product.name or "",
        ai.product.brand or "",
        ai.product.category or "",
        ai.country_of_origin or "",
    ]

    for declaration in ai.declarations:
        parts.append(str(declaration.field or ""))
        parts.append(str(declaration.value or ""))
        parts.extend(str(x) for x in declaration.evidence)

    return " ".join(parts).lower()


def _has_importer(ai: AIResult) -> bool:
    for declaration in ai.declarations:
        field = str(declaration.field or "").strip().lower()

        if field in {
            "importer",
            "importer_name",
            "importer_address",
        }:
            return bool(declaration.value)

    return False


def determine_context(ai: AIResult) -> PackageContext:
    text = _all_text(ai)

    category = str(ai.product.category or "").lower()
    name = str(ai.product.name or "").lower()

    imported = (
        _has_importer(ai)
        or bool(ai.country_of_origin)
        or "imported" in text
        or "country of origin" in text
        or "made in" in text and "india" not in text
    )

    food_words = [
        "food",
        "milk",
        "milkshake",
        "beverage",
        "drink",
        "juice",
        "snack",
        "biscuit",
        "cookie",
        "cereal",
        "rice",
        "flour",
        "spice",
        "edible",
        "confectionery",
        "chocolate",
        "namkeen",
        "oil",
    ]

    textile_words = [
        "textile",
        "garment",
        "hosiery",
        "shirt",
        "t-shirt",
        "trouser",
        "saree",
        "sari",
        "dhoti",
        "bedsheet",
        "bed sheet",
        "towel",
        "napkin",
        "pillow cover",
        "table cloth",
        "fabric",
        "cloth",
    ]

    sheet_words = [
        "foil",
        "facial tissue",
        "tissue",
        "toilet paper",
        "waxed paper",
        "paper sheet",
    ]

    container_words = [
        "container",
        "box",
        "bag",
        "bottle",
        "jar",
        "can",
        "tin",
        "pouch",
    ]

    wholesale_words = [
        "wholesale",
        "wholesale package",
        "not for retail sale",
        "not for individual sale",
    ]

    advertisement_words = [
        "advertisement",
        "advertising",
        "catalogue",
        "catalog",
        "offer price",
    ]

    pan_masala = "pan masala" in text

    return PackageContext(
        imported=imported,
        food=any(word in text or word in category or word in name for word in food_words),
        textile=any(word in text or word in category or word in name for word in textile_words),
        sheets=any(word in text for word in sheet_words),
        container=any(word in text for word in container_words),
        wholesale=any(word in text for word in wholesale_words),
        advertisement=any(word in text for word in advertisement_words),
        pan_masala=pan_masala,
        dimensions_relevant=any(
            word in text
            for word in [
                "dimension",
                "length",
                "width",
                "height",
                "depth",
                "diameter",
                "size",
            ]
        ),
        physical_verification_required=True,
    )


def origin_is_applicable(context: PackageContext) -> bool:
    return context.imported


def best_before_is_applicable(context: PackageContext) -> bool:
    return context.food


def dimensions_are_applicable(context: PackageContext) -> bool:
    return context.textile or context.dimensions_relevant
