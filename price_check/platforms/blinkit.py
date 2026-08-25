import asyncio
import urllib.parse

from playwright.async_api import Browser

from ..browser import new_stealth_context
from ..errors import PlatformError
from ..models import ProductResult

PLATFORM = "Blinkit"


async def search(browser: Browser, product: str, pincode: str, limit: int = 10, timeout_s: int = 45):
    context = await new_stealth_context(browser)
    page = await context.new_page()
    captured = []

    async def on_response(resp):
        try:
            if resp.request.method == "POST" and "v1/layout/search" in resp.url:
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype:
                    captured.append(await resp.json())
        except Exception:
            pass

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto("https://blinkit.com/", wait_until="domcontentloaded", timeout=timeout_s * 1000)
        await page.wait_for_timeout(2500)

        loc_input = page.locator(
            'input[name="select-locality"], input[placeholder*="search delivery location" i]'
        )
        await loc_input.first.click(timeout=10000)
        await loc_input.first.fill(pincode)
        await page.wait_for_timeout(2000)

        suggestion = page.locator('div[class*="LocationListContainer"]').first
        await suggestion.click(timeout=10000)
        await page.wait_for_timeout(2000)

        q = urllib.parse.quote(product)
        try:
            async with page.expect_response(
                lambda r: r.request.method == "POST" and "v1/layout/search" in r.url,
                timeout=20000,
            ):
                await page.goto(
                    f"https://blinkit.com/s/?q={q}", wait_until="domcontentloaded", timeout=timeout_s * 1000
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


def _parse(bodies, limit):
    results = []
    seen = set()
    for body in bodies:
        snippets = body.get("response", {}).get("snippets", [])
        for s in snippets:
            data = s.get("data", {})
            cart_item = data.get("atc_action", {}).get("add_to_cart", {}).get("cart_item")
            if not cart_item:
                continue
            key = (cart_item.get("product_id"), cart_item.get("unit"))
            if key in seen:
                continue
            seen.add(key)
            results.append(
                ProductResult(
                    platform=PLATFORM,
                    name=cart_item.get("display_name") or cart_item.get("product_name"),
                    brand=cart_item.get("brand"),
                    quantity=cart_item.get("unit"),
                    price=cart_item.get("price"),
                    mrp=cart_item.get("mrp"),
                    in_stock=(cart_item.get("inventory") or 0) > 0,
                )
            )
            if len(results) >= limit:
                return results
    return results
