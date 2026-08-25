import asyncio
import urllib.parse

from playwright.async_api import Browser

from ..browser import new_stealth_context
from ..errors import PlatformError
from ..models import ProductResult

PLATFORM = "Zepto"


async def search(browser: Browser, product: str, pincode: str, limit: int = 10, timeout_s: int = 45):
    context = await new_stealth_context(browser)
    page = await context.new_page()
    captured = []

    async def on_response(resp):
        try:
            if (
                resp.request.method == "POST"
                and "user-search-service/api/v3/search" in resp.url
                and "/filters" not in resp.url
            ):
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype:
                    captured.append(await resp.json())
        except Exception:
            pass

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto("https://www.zeptonow.com/", wait_until="domcontentloaded", timeout=timeout_s * 1000)
        await page.wait_for_timeout(3000)

        await page.get_by_text("Select Location", exact=False).first.click(timeout=10000)
        await page.wait_for_timeout(1000)

        inp = page.locator('input[type="text"]').first
        await inp.click(timeout=10000)
        await inp.fill(pincode)
        await page.wait_for_timeout(2000)

        await page.locator('[data-testid="address-search-item"]').first.click(timeout=10000)
        await page.wait_for_timeout(2000)

        q = urllib.parse.quote(product)
        try:
            async with page.expect_response(
                lambda r: r.request.method == "POST"
                and "user-search-service/api/v3/search" in r.url
                and "/filters" not in r.url,
                timeout=20000,
            ):
                await page.goto(
                    f"https://www.zeptonow.com/search?query={q}",
                    wait_until="domcontentloaded",
                    timeout=timeout_s * 1000,
                )
            await page.wait_for_timeout(1000)
        except Exception:
            pass
    except Exception as e:
        screenshot = None
        try:
            screenshot = await page.screenshot()
        except Exception:
            pass
        url = page.url
        await context.close()
        raise PlatformError(f"{PLATFORM}: {e}", screenshot=screenshot, url=url) from e

    await context.close()
    return _parse(captured, limit)


def _money(paise):
    if paise is None:
        return None
    return round(paise / 100, 2)


def _parse(bodies, limit):
    results = []
    seen = set()
    for body in bodies:
        for widget in body.get("layout", []):
            name = widget.get("widgetName", "")
            if not name.startswith("SEARCHED_PRODUCTS"):
                continue
            resolver = widget.get("data", {}).get("resolver", {})
            items = resolver.get("data", {}).get("items", [])
            for item in items:
                pr = item.get("productResponse")
                if not pr:
                    continue
                key = pr.get("id")
                if key in seen:
                    continue
                seen.add(key)
                prod = pr.get("product", {})
                variant = pr.get("productVariant", {})
                price = pr.get("sellingPrice") or pr.get("discountedSellingPrice")
                results.append(
                    ProductResult(
                        platform=PLATFORM,
                        name=prod.get("name"),
                        brand=prod.get("brand"),
                        quantity=variant.get("formattedPacksize"),
                        price=_money(price),
                        mrp=_money(pr.get("mrp")),
                        in_stock=not pr.get("outOfStock", False),
                    )
                )
                if len(results) >= limit:
                    return results
    return results
