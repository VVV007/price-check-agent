import asyncio
import os
import urllib.parse

from playwright.async_api import Browser

_DEBUG = os.environ.get("PRICECHECK_DEBUG") == "1"

from ..browser import new_stealth_context
from ..errors import PlatformError
from ..models import ProductResult

PLATFORM = "Swiggy Instamart"


async def search(browser: Browser, product: str, pincode: str, limit: int = 10, timeout_s: int = 45):
    context = await new_stealth_context(browser)
    page = await context.new_page()
    captured = []

    async def on_response(resp):
        try:
            if resp.request.method == "POST" and "api/instamart/search/v2" in resp.url:
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype:
                    captured.append(await resp.json())
        except Exception:
            pass

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto(
            "https://www.swiggy.com/instamart", wait_until="domcontentloaded", timeout=timeout_s * 1000
        )
        await page.wait_for_timeout(3000)

        if _DEBUG:
            await page.screenshot(path="dbg_im_1_home.png")

        await page.locator('[data-testid="search-location"]').first.click(timeout=10000)
        await page.wait_for_timeout(800)
        if _DEBUG:
            await page.screenshot(path="dbg_im_2_locclick.png")

        inp = page.locator("input").first
        await inp.click(timeout=10000)
        await inp.fill(pincode)
        await page.wait_for_timeout(2000)
        if _DEBUG:
            await page.screenshot(path="dbg_im_3_filled.png")

        await page.get_by_text(pincode, exact=True).first.click(timeout=10000)
        await page.wait_for_timeout(2500)
        if _DEBUG:
            await page.screenshot(path="dbg_im_4_suggest.png")

        await page.get_by_text("Confirm Location", exact=False).first.click(timeout=10000)
        await page.wait_for_timeout(3000)
        if _DEBUG:
            await page.screenshot(path="dbg_im_5_confirmed.png")

        q = urllib.parse.quote(product)
        try:
            async with page.expect_response(
                lambda r: r.request.method == "POST" and "api/instamart/search/v2" in r.url,
                timeout=20000,
            ):
                await page.goto(
                    f"https://www.swiggy.com/instamart/search?custom_back=true&query={q}",
                    wait_until="domcontentloaded",
                    timeout=timeout_s * 1000,
                )
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        if _DEBUG:
            await page.screenshot(path="dbg_im_6_search.png")
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


def _money(m):
    if not m:
        return None
    return round(int(m.get("units", 0)) + m.get("nanos", 0) / 1e9, 2)


def _iter_item_lists(cards):
    for c in cards:
        inner = c.get("card", {}).get("card", {})
        if "items" in inner:
            yield inner["items"]
        grid = inner.get("gridElements", {}).get("infoWithStyle", {})
        if "items" in grid:
            yield grid["items"]


def _parse(bodies, limit):
    results = []
    seen = set()
    for body in bodies:
        cards = body.get("data", {}).get("cards", [])
        for items in _iter_item_lists(cards):
            for item in items:
                variations = item.get("variations") or []
                if not variations:
                    continue
                v = variations[0]
                key = v.get("skuId")
                if key in seen:
                    continue
                seen.add(key)
                price = v.get("price", {})
                results.append(
                    ProductResult(
                        platform=PLATFORM,
                        name=item.get("displayName"),
                        brand=item.get("brand"),
                        quantity=v.get("quantityDescription"),
                        price=_money(price.get("offerPrice")),
                        mrp=_money(price.get("mrp")),
                        in_stock=item.get("inStock", True) and item.get("isAvail", True),
                    )
                )
                if len(results) >= limit:
                    return results
    return results
