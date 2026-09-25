from io import StringIO
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


URL = (
    "https://stats-api-01.pba.ph/tournaments/"
    "pba-season-49-governors-cup?game_id=3"
)


def scrape_box_score(url: str) -> list[pd.DataFrame]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1000},
        )

        page = context.new_page()
        page.set_default_timeout(30_000)

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response is not None:
            print("HTTP status:", response.status)

        print("Page title:", page.title())

        try:
            # Wait for the page's JavaScript to render a table.
            page.wait_for_selector(
                "table",
                state="attached",
                timeout=30_000,
            )
        except PlaywrightTimeoutError:
            # Save debugging information before failing.
            page.screenshot(
                path="pba_debug.png",
                full_page=True,
            )

            Path("pba_debug.html").write_text(
                page.content(),
                encoding="utf-8",
            )

            raise RuntimeError(
                "The page loaded, but no table appeared. "
                "Check pba_debug.png and pba_debug.html."
            )

        html = page.content()

        Path("pba_game_3.html").write_text(
            html,
            encoding="utf-8",
        )

        browser.close()

    return pd.read_html(StringIO(html))


if __name__ == "__main__":
    tables = scrape_box_score(URL)

    print(f"Found {len(tables)} tables")

    for index, dataframe in enumerate(tables):
        print(f"\nTable {index}")
        print(dataframe.head())

        dataframe.to_csv(
            f"pba_game_3_table_{index}.csv",
            index=False,
        )