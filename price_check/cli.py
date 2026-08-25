import argparse
import asyncio
import csv
import sys

from playwright.async_api import async_playwright

from .platforms import blinkit, zepto, instamart
from .models import ProductResult

PLATFORMS = [blinkit, zepto, instamart]


async def run(product: str, pincode: str, limit: int):
    results_by_platform = {}
    errors = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])

        async def run_one(module):
            last_error = None
            for attempt in range(2):
                try:
                    results = await module.search(browser, product, pincode, limit=limit)
                    if results:
                        results_by_platform[module.PLATFORM] = results
                        return
                    last_error = "no results returned"
                except Exception as e:
                    last_error = str(e)
            errors[module.PLATFORM] = last_error

        await asyncio.gather(*(run_one(m) for m in PLATFORMS))
        await browser.close()

    return results_by_platform, errors


def print_table(results_by_platform: dict, errors: dict):
    all_results: list[ProductResult] = []
    for items in results_by_platform.values():
        all_results.extend(items)

    if not all_results:
        print("No results found on any platform.")
    else:
        name_w = min(45, max(len(r.name or "") for r in all_results) + 2)
        header = f"{'Platform':<18}{'Product':<{name_w}}{'Qty':<14}{'Price':>9}{'MRP':>9}{'Off':>7}  Stock"
        print(header)
        print("-" * len(header))
        for platform in results_by_platform:
            for r in sorted(results_by_platform[platform], key=lambda x: (x.price is None, x.price)):
                name = (r.name or "")[: name_w - 2]
                price = f"₹{r.price:.0f}" if r.price is not None else "-"
                mrp = f"₹{r.mrp:.0f}" if r.mrp is not None else "-"
                off = f"{r.discount_percent:.0f}%" if r.discount_percent else "-"
                stock = "Yes" if r.in_stock else "No"
                print(f"{r.platform:<18}{name:<{name_w}}{(r.quantity or '-'):<14}{price:>9}{mrp:>9}{off:>7}  {stock}")

    if errors:
        print("\nPlatforms that failed:")
        for platform, msg in errors.items():
            print(f"  - {platform}: {msg}")


def write_csv(path: str, results_by_platform: dict):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["platform", "name", "brand", "quantity", "price", "mrp", "discount_percent", "in_stock"])
        for items in results_by_platform.values():
            for r in items:
                writer.writerow(
                    [r.platform, r.name, r.brand, r.quantity, r.price, r.mrp, r.discount_percent, r.in_stock]
                )


def main():
    parser = argparse.ArgumentParser(description="Check product prices across quick-commerce platforms.")
    parser.add_argument("product", help='Product to search for, e.g. "amul butter"')
    parser.add_argument("--pincode", required=True, help="Delivery pincode to check prices for")
    parser.add_argument("--limit", type=int, default=10, help="Max results per platform (default: 10)")
    parser.add_argument("--csv", dest="csv_path", help="Write results to a CSV file at this path")
    args = parser.parse_args()

    results_by_platform, errors = asyncio.run(run(args.product, args.pincode, args.limit))
    print_table(results_by_platform, errors)

    if args.csv_path:
        write_csv(args.csv_path, results_by_platform)
        print(f"\nSaved to {args.csv_path}")

    if not results_by_platform:
        sys.exit(1)


if __name__ == "__main__":
    main()
