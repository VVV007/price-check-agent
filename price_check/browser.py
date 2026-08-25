from playwright.async_api import Browser

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['en-IN','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
"""


async def new_stealth_context(browser: Browser):
    context = await browser.new_context(
        viewport={"width": 1366, "height": 900},
        locale="en-IN",
        user_agent=USER_AGENT,
        extra_http_headers={"accept-language": "en-IN,en;q=0.9"},
    )
    await context.add_init_script(STEALTH_INIT_SCRIPT)
    return context
