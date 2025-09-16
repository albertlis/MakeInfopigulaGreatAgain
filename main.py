import json
import logging
import os
import smtplib
import time
from datetime import datetime, timedelta  # added timedelta

import schedule
import yagmail
from datetime import timezone
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Page

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# General
URL = "https://infopigula.pl/#/"
DATA_FILE = "data.json"
LOG_FILE = "scraper.log"
STATE_FILE = "state.json"  # new: track last successful scrape

# Email settings from .env
SMTP_USER = os.getenv("SRC_MAIL")
SMTP_PASSWORD = os.getenv("SRC_PWD")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
RECIPIENT_EMAIL = os.getenv("DST_MAIL")

# Scraping
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
HEADLESS_MODE = True
BROWSER_TYPE = os.getenv("BROWSER_TYPE", "chromium").lower()
VIVALDI_PATH = os.getenv("VIVALDI_PATH")
# New: list of tab labels to scrape (match visible text in p-tab)
TABS_TO_SCRAPE = ["Polska", "Świat"]  # Extend e.g. ["Polska", "Świat", "Pozytywy"]

# --- Optimization / Tuning Flags (new) ---
ENABLE_RESOURCE_BLOCK = os.getenv("ENABLE_RESOURCE_BLOCK", "1") == "1"
ENABLE_DEBUG_SELECTORS = os.getenv("ENABLE_DEBUG_SELECTORS", "0") == "1"
MAX_PAGE_LOAD_RETRIES = int(os.getenv("MAX_PAGE_LOAD_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("RETRY_BACKOFF_SECONDS", "3"))
PAGE_DEFAULT_TIMEOUT_MS = int(os.getenv("PAGE_DEFAULT_TIMEOUT_MS", "15000"))

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)


# --- Data Storage ---
def load_data() -> list:
    """Loads scraped data from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Could not read data file {DATA_FILE}: {e}")
        return []


def save_data(data: list) -> None:
    """Saves data to the JSON file (atomic write)."""
    try:
        tmp_path = f"{DATA_FILE}.tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DATA_FILE)
    except IOError as e:
        logging.error(f"Could not write to data file {DATA_FILE}: {e}")


# --- State Management ---
def load_state() -> dict:
    """Loads scrape state (e.g., last successful scrape timestamp)."""
    if not os.path.exists(STATE_FILE):
        return {"last_successful_scrape": None}
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Could not read state file {STATE_FILE}: {e}")
        return {"last_successful_scrape": None}


def save_state(state: dict) -> None:
    """Saves scrape state to the state file."""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Could not write state file {STATE_FILE}: {e}")


def mark_successful_scrape() -> None:
    """Marks the current scrape as successful by updating the state file."""
    state = load_state()
    state["last_successful_scrape"] = datetime.now(timezone.utc).isoformat()
    save_state(state)


# --- Scraping Logic ---
def click_tab(page: Page, tab_name: str) -> str | None:
    """
    Clicks a tab by its visible label (text content of <p-tab>) and returns the
    CSS selector for its controlled panel (via aria-controls), or None if not found.
    """
    tab_locator = page.locator("div.p-tablist-tab-list").locator("p-tab", has_text=tab_name).first
    try:
        tab_locator.wait_for(state="visible", timeout=10000)
    except PlaywrightTimeoutError:
        logging.error(f"Tab '{tab_name}' not found.")
        return None

    tab_locator.click()
    # Wait until aria-selected becomes true
    for _ in range(20):
        if tab_locator.get_attribute("aria-selected") == "true":
            break
        page.wait_for_timeout(250)
    panel_id = tab_locator.get_attribute("aria-controls")
    return f"#{panel_id}" if panel_id else None


def scrape_tab_content(page: Page, tab_name: str) -> list:
    """
    Scrapes article content from a specific tab using the new <p-tab> structure.
    Tries multiple fallback selectors to adapt to future minor changes.
    """
    logging.info(f"Scraping tab: {tab_name}")
    panel_selector = click_tab(page, tab_name)
    container = None
    if panel_selector:
        try:
            page.wait_for_selector(panel_selector, timeout=10000)
            container = page.query_selector(panel_selector)
        except PlaywrightTimeoutError:
            logging.warning(f"Panel for tab '{tab_name}' did not appear. Falling back to full page.")
    if not container:
        container = page

    # Potential article selectors (ordered by specificity)
    # Updated: new structure uses app-news-content with span.news-content-data
    candidate_selectors = [
        "app-news-content span.news-content-data",   # NEW primary selector
        "app-news-content .news-content-data",       # fallback (class only)
        "app-news-content",                          # whole component if inner span missing
        ".news-container",                           # container div
        ".article__item",                            # legacy
        "[data-article-id]",
        "app-article-item",
        ".article-item"
    ]

    articles = []
    seen_texts = set()

    for sel in candidate_selectors:
        elements = container.query_selector_all(sel)
        if not elements:
            continue
        for el in elements:
            # If selector matched the inner span, keep it; else try to find the span for cleaner text.
            content_el = (
                el if "news-content-data" in sel
                else el.query_selector("span.news-content-data") or el
            )

            raw_text = content_el.inner_text().strip() or content_el.inner_html().strip()
            if not raw_text:
                continue

            # Normalize: collapse multi-line paragraphs and excessive whitespace.
            normalized_text = " ".join(t.strip() for t in raw_text.splitlines() if t.strip())
            if not normalized_text:
                continue

            # Skip obvious non-article promotional cards (heuristic)
            if normalized_text.startswith("Codziennie o 6 rano"):
                continue

            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)

            article_id = (
                el.get_attribute("id")
                or el.get_attribute("data-article-id")
                or str(abs(hash(normalized_text)))
            )

            articles.append({
                "id": article_id,
                "content": normalized_text,
                "category": tab_name
            })

        if articles:
            break  # stop at first selector yielding results

    if not articles:
        logging.warning(f"No articles found in tab '{tab_name}' (checked new structure selectors).")
    return articles


def scrape_both_tabs(page: Page):
    """
    Scrapes articles from configured tabs (TABS_TO_SCRAPE) and merges them into storage.
    """
    all_new = []
    for tab in TABS_TO_SCRAPE:
        try:
            all_new.extend(scrape_tab_content(page, tab))
        except Exception as e:
            logging.error(f"Error while scraping tab '{tab}': {e}", exc_info=True)

    existing_data = load_data()
    # Use dict for faster dedup (id -> record)
    merged = {a['id']: a for a in existing_data}
    added_count = 0
    for a in all_new:
        if a['id'] not in merged:
            merged[a['id']] = a
            added_count += 1
    if added_count:
        # Optional compaction: keep deterministic order (by category then id)
        new_list = sorted(merged.values(), key=lambda x: (x['category'], x['id']))
        save_data(new_list)
    logging.info(f"Scraping finished. Added {added_count} new articles.")


def _configure_page(page: Page):
    """Apply performance tweaks (resource blocking, timeouts)."""
    page.set_default_timeout(PAGE_DEFAULT_TIMEOUT_MS)
    if ENABLE_RESOURCE_BLOCK:
        def route_handler(route):
            rtype = route.request.resource_type
            if rtype in ("image", "media", "font"):
                return route.abort()
            route.continue_()
        page.route("**/*", route_handler)


def _load_with_retries(page: Page, url: str) -> bool:
    """Retry page load with backoff."""
    for attempt in range(1, MAX_PAGE_LOAD_RETRIES + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("div.p-tablist-tab-list", timeout=30000)
            return True
        except PlaywrightTimeoutError:
            logging.warning(f"Load attempt {attempt} failed.")
        except Exception as e:
            logging.warning(f"Load attempt {attempt} error: {e}")
        if attempt < MAX_PAGE_LOAD_RETRIES:
            sleep_time = RETRY_BACKOFF_SECONDS * attempt
            logging.info(f"Retrying in {sleep_time:.1f}s...")
            time.sleep(sleep_time)
    return False


def daily_scrape() -> None:
    """Main daily scraping task."""
    start_ts = time.perf_counter()
    logging.info("Starting daily scrape job.")
    success_loaded = False  # new flag
    with sync_playwright() as p:
        try:
            browser_options = {"headless": HEADLESS_MODE}
            if BROWSER_TYPE == "edge":
                logging.info("Using Edge browser.")
                browser_options["channel"] = "msedge"
            elif BROWSER_TYPE == "vivaldi":
                if not VIVALDI_PATH or not os.path.exists(VIVALDI_PATH):
                    logging.error("Vivaldi path is not configured or invalid. Please set VIVALDI_PATH in .env file.")
                    return
                logging.info(f"Using Vivaldi browser from: {VIVALDI_PATH}")
                browser_options["executable_path"] = VIVALDI_PATH
            else:  # default to chromium
                logging.info("Using Chromium browser.")
            browser = p.chromium.launch(**browser_options)
            page = browser.new_page(user_agent=USER_AGENT)
            _configure_page(page)
            success_loaded = _load_with_retries(page, URL)
            if not success_loaded:
                logging.error("All page load attempts failed. Aborting.")
                browser.close()
                return
        except Exception as e:
            logging.error(f"An error occurred during browser setup: {e}")
            return

        try:
            scrape_both_tabs(page)
        except Exception as e:
            logging.error(f"An error occurred during scraping: {e}", exc_info=True)
        finally:
            browser.close()

    if success_loaded:
        mark_successful_scrape()
        elapsed = time.perf_counter() - start_ts
        logging.info(f"Recorded successful page load. Total scrape time: {elapsed:.2f}s")


# --- Emailing ---
def send_weekly_summary() -> None:
    """Compiles and sends the weekly summary email, then clears the data file."""
    logging.info("Starting weekly summary job.")

    # Safety: ensure only runs once a week even if mis-scheduled
    if datetime.now().weekday() != 5:  # 5 = Saturday
        logging.info("Not Saturday; skipping weekly summary.")
        return

    # Skip if no successful scrape in last 7 days
    state = load_state()
    last_success_iso = state.get("last_successful_scrape")
    if not last_success_iso:
        logging.info("No successful scrapes recorded. Skipping email.")
        return
    try:
        last_success = datetime.fromisoformat(last_success_iso)
    except ValueError:
        logging.warning("Invalid last_successful_scrape timestamp. Skipping email.")
        return
    if last_success < datetime.now(timezone.utc) - timedelta(days=7):
        logging.info("No successful scrapes within last 7 days. Skipping email.")
        return

    weekly_data = load_data()
    if not weekly_data:
        logging.info("No new articles this week. Skipping email.")
        return

    # Format email content
    polska_html = "".join([f"<p>{a['content']}</p><hr>" for a in weekly_data if a['category'] == 'Polska'])
    swiat_html = "".join([f"<p>{a['content']}</p><hr>" for a in weekly_data if a['category'] == 'Świat'])

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Infopiguła Tygodniowe Podsumowanie</title>
    </head>
    <body>
        <h1>Tygodniowe podsumowanie z Infopiguły</h1>
        <h2>Polska</h2>
        {polska_html or "<p>Brak wiadomości z Polski w tym tygodniu.</p>"}
        <br>
        <h2>Świat</h2>
        {swiat_html or "<p>Brak wiadomości ze Świata w tym tygodniu.</p>"}
    </body>
    </html>
    """

    try:
        yag = yagmail.SMTP(SMTP_USER, SMTP_PASSWORD, port=SMTP_PORT, smtp_starttls=True, smtp_ssl=False)
        yag.send(
            to=RECIPIENT_EMAIL,
            subject=f"Infopiguła Podsumowanie Tygodnia - {datetime.now().strftime('%Y-%m-%d')}",
            contents=html_content
        )
        logging.info("Weekly summary email sent successfully.")

        # Clear data file after successful send
        save_data([])
        logging.info("Data file cleared for the next week.")

    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP Authentication failed. Check email credentials in .env file.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}", exc_info=True)


# --- Scheduler ---
def run_scheduler() -> None:
    """Sets up and runs the daily and weekly jobs."""
    logging.info("Scheduler started.")

    # Schedule daily scraping
    schedule.every().day.at("10:00").do(daily_scrape)

    # Schedule weekly email summary
    schedule.every().saturday.at("12:00").do(send_weekly_summary)

    logging.info(f"Next daily scrape at: {schedule.jobs[0].next_run}")
    logging.info(f"Next weekly summary at: {schedule.jobs[1].next_run}")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    # On first run, you might need to install playwright's browsers
    # In your terminal, run: python -m playwright install
    logging.info("Script started. To stop, press Ctrl+C.")

    # Optional: Run a scrape immediately on startup
    logging.info("Performing initial scrape on startup...")
    daily_scrape()

    try:
        run_scheduler()
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user.")
    except Exception as e:
        logging.error(f"An unexpected error occurred in the scheduler: {e}", exc_info=True)
