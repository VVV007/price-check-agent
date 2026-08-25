import json
from typing import List, Literal

from google import genai
from pydantic import BaseModel

MODEL = "gemini-3.6-flash"


class ParsedItem(BaseModel):
    query: str
    display_name: str
    quantity: int = 1


class ParsedShoppingList(BaseModel):
    items: List[ParsedItem]


# Gemini's structured-output schema support does not reliably handle Pydantic's
# `Optional[...]` fields (serialized as `anyOf: [X, {"type": "null"}]`) — nested
# `$ref`/`$defs` alone work fine, but adding nullable fields caused it to silently
# collapse the response (duplicated/truncated items) instead of erroring. So every
# field below is required, using sentinel values ("" / -1 / "none") instead of null.
class PlatformMatch(BaseModel):
    found: bool
    name: str = ""
    price: float = -1
    quantity_label: str = ""


class ItemComparison(BaseModel):
    requested: str
    quantity: int
    blinkit: PlatformMatch
    zepto: PlatformMatch
    swiggy_instamart: PlatformMatch
    cheapest_platform: Literal["Blinkit", "Zepto", "Swiggy Instamart", "none"]


class PlatformTotal(BaseModel):
    total: float
    missing_items: List[str]


class ComparisonReport(BaseModel):
    items: List[ItemComparison]
    blinkit_total: PlatformTotal
    zepto_total: PlatformTotal
    swiggy_instamart_total: PlatformTotal
    optimal_mixed_total: float
    summary: str


def _structured_call(api_key: str, prompt: str, schema_model: type[BaseModel]) -> BaseModel:
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=MODEL,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": schema_model.model_json_schema(),
        },
    )
    return schema_model.model_validate_json(interaction.output_text)


def parse_shopping_list(api_key: str, text: str) -> List[ParsedItem]:
    prompt = (
        "Parse this shopping list into individual items to search for on Indian "
        "quick-commerce grocery apps. For each item, give a short concrete search "
        "query (e.g. 'amul butter', 'toothpaste', 'maggi noodles'), a human-readable "
        "display name, and the quantity the user wants (default 1).\n\n"
        f"{text}"
    )
    parsed = _structured_call(api_key, prompt, ParsedShoppingList)
    return parsed.items


def build_comparison_report(api_key: str, results_by_item: list) -> ComparisonReport:
    """
    results_by_item: list of dicts, each:
        {"requested": str, "quantity": int,
         "results": {platform_name: [{"name", "quantity", "price", "mrp", "in_stock"}, ...]}}
    """
    payload = json.dumps(results_by_item, ensure_ascii=False, default=str)
    prompt = (
        "Here is a shopping list and, for each requested item, the raw search "
        "results found on three quick-commerce platforms: Blinkit, Zepto, and "
        "Swiggy Instamart. You MUST return exactly one ItemComparison entry for "
        "EVERY requested item, in the same order, even if no good match was found "
        "for it. For each requested item, pick the single best-matching real "
        "product from each platform's results (same brand/type and closest pack "
        "size wherever possible). If a platform has no reasonable match, set that "
        "platform's found=false, name=\"\", price=-1, quantity_label=\"\" — never "
        "omit the platform object itself. Set cheapest_platform to \"none\" if no "
        "platform has a match. Then compute, for each platform, the total cost of "
        "buying every requested item from that platform alone (only summing items "
        "actually found there; list any requested items missing from that platform "
        "by name in missing_items, or an empty list if none are missing), and "
        "separately the cheapest possible total if each item is bought from "
        "whichever platform has it cheapest (optimal_mixed_total). Write a short, "
        "friendly 2-4 sentence recommendation as the summary.\n\n"
        f"{payload}"
    )
    return _structured_call(api_key, prompt, ComparisonReport)
