from typing import List, Literal, Optional

from anthropic import Anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5"


class ParsedItem(BaseModel):
    query: str
    display_name: str
    quantity: int = 1


class ParsedShoppingList(BaseModel):
    items: List[ParsedItem]


class PlatformMatch(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    quantity_label: Optional[str] = None


class ItemComparison(BaseModel):
    requested: str
    quantity: int
    blinkit: Optional[PlatformMatch] = None
    zepto: Optional[PlatformMatch] = None
    swiggy_instamart: Optional[PlatformMatch] = None
    cheapest_platform: Optional[Literal["Blinkit", "Zepto", "Swiggy Instamart"]] = None


class PlatformTotal(BaseModel):
    total: float
    missing_items: List[str] = []


class ComparisonReport(BaseModel):
    items: List[ItemComparison]
    blinkit_total: PlatformTotal
    zepto_total: PlatformTotal
    swiggy_instamart_total: PlatformTotal
    optimal_mixed_total: float
    summary: str


def parse_shopping_list(api_key: str, text: str) -> List[ParsedItem]:
    client = Anthropic(api_key=api_key)
    response = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Parse this shopping list into individual items to search for on Indian "
                    "quick-commerce grocery apps. For each item, give a short concrete search "
                    "query (e.g. 'amul butter', 'toothpaste', 'maggi noodles'), a human-readable "
                    "display name, and the quantity the user wants (default 1).\n\n"
                    f"{text}"
                ),
            }
        ],
        output_format=ParsedShoppingList,
    )
    return response.parsed_output.items


def build_comparison_report(api_key: str, results_by_item: list) -> ComparisonReport:
    """
    results_by_item: list of dicts, each:
        {"requested": str, "quantity": int,
         "results": {platform_name: [{"name", "quantity", "price", "mrp", "in_stock"}, ...]}}
    """
    import json

    client = Anthropic(api_key=api_key)
    payload = json.dumps(results_by_item, ensure_ascii=False, default=str)
    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    "Here is a shopping list and, for each requested item, the raw search "
                    "results found on three quick-commerce platforms: Blinkit, Zepto, and "
                    "Swiggy Instamart. For each requested item, pick the single best-matching "
                    "real product from each platform's results (same brand/type and closest "
                    "pack size wherever possible; leave a platform's field null if nothing "
                    "reasonably matches). Then compute, for each platform, the total cost of "
                    "buying every requested item from that platform alone (list any requested "
                    "items missing from that platform in missing_items), and separately the "
                    "cheapest possible total if each item is bought from whichever platform has "
                    "it cheapest (optimal_mixed_total). Write a short, friendly 2-4 sentence "
                    "recommendation as the summary.\n\n"
                    f"{payload}"
                ),
            }
        ],
        output_format=ComparisonReport,
    )
    return response.parsed_output
