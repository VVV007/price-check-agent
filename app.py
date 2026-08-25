import asyncio
import subprocess
import sys
import threading

import streamlit as st

st.set_page_config(page_title="Quick Commerce Price Checker", page_icon="🛒", layout="wide")


@st.cache_resource
def _ensure_chromium_installed():
    # Streamlit Community Cloud only pip-installs requirements.txt; it never runs
    # `playwright install`. st.cache_resource makes this run exactly once per
    # server process (not on every rerun/user), downloading Chromium on cold start.
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    return True


_ensure_chromium_installed()

from price_check.cli import run as run_search  # noqa: E402

# Each search drives real headless-browser sessions, which is heavy on a small shared
# server. Cap it to one search at a time server-wide so concurrent friends queue up
# instead of all launching browsers simultaneously and starving the box.
_SEARCH_SLOT = threading.Semaphore(1)

PLATFORM_COLOR = {
    "Blinkit": "#f8cb46",
    "Zepto": "#8b2fc9",
    "Swiggy Instamart": "#fc8019",
}
PLATFORM_TEXT = {
    "Blinkit": "#1a1a1a",
    "Zepto": "#ffffff",
    "Swiggy Instamart": "#ffffff",
}

st.markdown(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
    }
    .platform-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .02em;
        margin-bottom: 6px;
    }
    .price-big {
        font-size: 26px;
        font-weight: 700;
        margin: 0;
        line-height: 1.2;
    }
    .mrp-strike {
        text-decoration: line-through;
        opacity: 0.55;
        font-size: 13px;
    }
    .discount-tag {
        color: #1a9c4b;
        font-weight: 600;
        font-size: 13px;
    }
    .oos-tag {
        color: #d64545;
        font-weight: 600;
        font-size: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "basket" not in st.session_state:
    st.session_state.basket = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "errors" not in st.session_state:
    st.session_state.errors = {}
if "last_query" not in st.session_state:
    st.session_state.last_query = ""

st.title("🛒 Quick Commerce Price Checker")
st.caption("Blinkit · Zepto · Swiggy Instamart — compare live prices side by side")

with st.sidebar:
    st.header("Settings")
    pincode = st.text_input("Delivery pincode", value=st.session_state.get("pincode", ""))
    st.session_state.pincode = pincode
    limit = st.slider("Results per platform", min_value=3, max_value=20, value=8)

    st.divider()
    st.header(f"🧺 Basket ({len(st.session_state.basket)})")

    if st.session_state.basket:
        totals = {}
        for i, item in enumerate(st.session_state.basket):
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"**{item['name']}**")
                c1.caption(f"{item['platform']} · {item['quantity'] or '-'} · ₹{item['price']:.0f}")
                if c2.button("✕", key=f"remove_{i}", use_container_width=True):
                    st.session_state.basket.pop(i)
                    st.rerun()
            totals[item["platform"]] = totals.get(item["platform"], 0) + (item["price"] or 0)

        st.subheader("Total by platform")
        cheapest_platform = min(totals, key=totals.get)
        for platform, total in sorted(totals.items(), key=lambda x: x[1]):
            tag = " 🏆" if platform == cheapest_platform else ""
            st.markdown(f"**{platform}**: ₹{total:.0f}{tag}")

        if st.button("Clear basket", use_container_width=True):
            st.session_state.basket = []
            st.rerun()
    else:
        st.caption("No items yet. Search below and add products.")

col1, col2 = st.columns([4, 1])
product = col1.text_input("Search for a product", placeholder='e.g. "amul butter"', label_visibility="collapsed")
search_clicked = col2.button("Search", use_container_width=True)

if search_clicked:
    if not pincode:
        st.error("Enter a delivery pincode in the sidebar first.")
    elif not product:
        st.error("Enter a product to search for.")
    else:
        busy = not _SEARCH_SLOT.acquire(timeout=0.1)
        if busy:
            with st.spinner("Another search is in progress on this server — waiting for your turn..."):
                _SEARCH_SLOT.acquire()
        try:
            with st.spinner(f'Checking prices for "{product}" across platforms...'):
                results, errors = asyncio.run(run_search(product, pincode, limit))
            st.session_state.results = results
            st.session_state.errors = errors
            st.session_state.last_query = product
        finally:
            _SEARCH_SLOT.release()

if st.session_state.results:
    st.subheader(f'Results for "{st.session_state.last_query}"')

    # --- quick compare: cheapest match per platform ---
    cheapest = {}
    for platform, items in st.session_state.results.items():
        priced = [r.price for r in items if r.price is not None]
        if priced:
            cheapest[platform] = min(priced)
    if cheapest:
        overall_min = min(cheapest.values())
        metric_cols = st.columns(len(PLATFORM_COLOR))
        for mcol, platform in zip(metric_cols, PLATFORM_COLOR):
            price = cheapest.get(platform)
            with mcol:
                if price is None:
                    st.metric(platform, "-")
                else:
                    diff = price - overall_min
                    mcol.metric(
                        platform,
                        f"₹{price:.0f}",
                        delta=("Cheapest 🏆" if diff == 0 else f"+₹{diff:.0f} vs cheapest"),
                        delta_color="normal" if diff == 0 else "inverse",
                    )
        st.divider()

    # --- side-by-side product cards per platform ---
    columns = st.columns(len(PLATFORM_COLOR))
    for pcol, platform in zip(columns, PLATFORM_COLOR):
        with pcol:
            color = PLATFORM_COLOR[platform]
            text_color = PLATFORM_TEXT[platform]
            st.markdown(
                f'<span class="platform-badge" style="background:{color};color:{text_color};">{platform}</span>',
                unsafe_allow_html=True,
            )
            items = st.session_state.results.get(platform, [])
            if platform in st.session_state.errors:
                info = st.session_state.errors[platform]
                st.error(info["message"])
                if info.get("screenshot"):
                    with st.expander("Show what the page looked like"):
                        if info.get("url"):
                            st.caption(info["url"])
                        st.image(info["screenshot"])
                continue
            if not items:
                st.caption("No results.")
                continue

            for idx, r in enumerate(sorted(items, key=lambda x: (x.price is None, x.price))):
                with st.container(border=True):
                    st.markdown(f"**{r.name}**")
                    st.caption(r.quantity or "-")
                    price_txt = f"₹{r.price:.0f}" if r.price is not None else "-"
                    st.markdown(f'<p class="price-big">{price_txt}</p>', unsafe_allow_html=True)

                    if r.mrp is not None and r.discount_percent:
                        st.markdown(
                            f'<span class="mrp-strike">₹{r.mrp:.0f}</span> '
                            f'<span class="discount-tag">{r.discount_percent:.0f}% off</span>',
                            unsafe_allow_html=True,
                        )
                    if not r.in_stock:
                        st.markdown('<span class="oos-tag">Out of stock</span>', unsafe_allow_html=True)

                    if st.button(
                        "Add to basket",
                        key=f"add_{platform}_{idx}",
                        use_container_width=True,
                        disabled=not r.in_stock,
                    ):
                        st.session_state.basket.append(
                            {
                                "platform": r.platform,
                                "name": r.name,
                                "quantity": r.quantity,
                                "price": r.price,
                                "mrp": r.mrp,
                            }
                        )
                        st.toast(f"Added {r.name} ({platform}) to basket")
