import json
import logging
import os
import smtplib
import time
from datetime import datetime

import schedule
import yagmail
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Page

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# General
URL = "https://infopigula.pl/#/"
DATA_FILE = "data.json"
LOG_FILE = "scraper.log"

# Email settings from .env
SMTP_USER = os.getenv("SRC_MAIL")
SMTP_PASSWORD = os.getenv("SRC_PWD")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
RECIPIENT_EMAIL = os.getenv("DST_MAIL")

# Scraping
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
HEADLESS_MODE = True  # Set to False for debugging
BROWSER_TYPE = os.getenv("BROWSER_TYPE", "chromium").lower()  # chromium, edge, or vivaldi
VIVALDI_PATH = os.getenv("VIVALDI_PATH")  # Required if BROWSER_TYPE is 'vivaldi'

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
    """Saves data to the JSON file."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logging.error(f"Could not write to data file {DATA_FILE}: {e}")


# --- Scraping Logic ---
def scrape_tab_content(page: Page, tab_name: str) -> list:
    """Scrapes article content from a specific tab ('Polska' or 'Świat')."""
    logging.info(f"Scraping tab: {tab_name}")
    tab_selector = "#poland" if tab_name == "Polska" else "#global"
    page.click(tab_selector)
    page.wait_for_timeout(2000)  # Wait for content to switch

    articles = []
    article_elements = page.query_selector_all(".article__item")
    for element in article_elements:
        article_id = element.get_attribute("id")
        if content_element := element.query_selector(".article__content"):
            html_content = content_element.inner_html()
            # Clean up the content a bit
            if "<span>" in html_content:
                html_content = html_content.split("<span>")[1].split("</span>")[0]
            articles.append({"id": article_id, "content": html_content.strip(), "category": tab_name})
    return articles


def daily_scrape() -> None:
    """Main daily scraping task."""
    logging.info("Starting daily scrape job.")
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
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("#poland", timeout=30000)
        except PlaywrightTimeoutError:
            logging.error("Failed to load the initial page. Aborting scrape.")
            return
        except Exception as e:
            logging.error(f"An error occurred during browser setup: {e}")
            return

        try:
            # Scrape both tabs
            polska_articles = scrape_tab_content(page, "Polska")
            swiat_articles = scrape_tab_content(page, "Świat")
            new_articles = polska_articles + swiat_articles

            # Aggregate data
            existing_data = load_data()
            existing_ids = {article['id'] for article in existing_data}

            added_count = 0
            for article in new_articles:
                if article['id'] not in existing_ids:
                    existing_data.append(article)
                    existing_ids.add(article['id'])
                    added_count += 1

            if added_count > 0:
                save_data(existing_data)
            logging.info(f"Scraping finished. Added {added_count} new articles.")

        except Exception as e:
            logging.error(f"An error occurred during scraping: {e}", exc_info=True)
        finally:
            browser.close()


# --- Emailing ---
def send_weekly_summary() -> None:
    """Compiles and sends the weekly summary email, then clears the data file."""
    logging.info("Starting weekly summary job.")

    if not all([SMTP_USER, SMTP_PASSWORD, RECIPIENT_EMAIL]):
        logging.error("Email configuration is incomplete. Cannot send email.")
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
