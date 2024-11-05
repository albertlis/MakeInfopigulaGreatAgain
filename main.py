import logging
import os
import platform
import time

import schedule as schedule
import yagmail as yagmail
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def scroll_to_bottom(driver: WebDriver, num_scrolls: int) -> None:
    for _ in range(num_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)


# def get_driver() -> webdriver.Chrome:
#     op = webdriver.ChromeOptions()
#     op.add_argument('--headless')
#     op.add_argument("window-size=1920,1080")  # Specify resolution
#     # options.add_argument("--no-sandbox")
#     # options.add_argument("--disable-dev-shm-usage")
#     # options.add_argument("--disable-gpu")

#     # Define a user agent
#     op.add_argument(
#         "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/2b7c7"
#     )
#     return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=op)

def get_driver() -> webdriver.Chrome:
    system = platform.system()
    if system not in {"Windows", "Linux"}:
        raise ValueError("This driver only works on Windows and Linux systems.")

    browser = 'chrome' if system == "Linux" else 'edge'

    options = webdriver.ChromeOptions() if browser == 'chrome' else webdriver.EdgeOptions()
    options.add_argument("window-size=1400,1080")
    options.add_argument("--disk-cache-size=10485760")
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins-discovery")

    if browser == 'chrome':
        options.binary_location = "/usr/bin/chromium-browser"
    # Disable loading images for better performance
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/2b7c7"
    )
    if browser == "chrome":
        return webdriver.Chrome(options, Service(executable_path="/usr/bin/chromedriver"))
    else:
        return webdriver.Chrome(options=options)


def get_news(driver: WebDriver) -> str:
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.find_all('div', class_='article__content')
    spans = [art.find_all('span') for art in articles]
    spans = [span[0] for span in spans if span]
    spans = [f'{span.prettify()} <hr>' for span in spans if span]
    html = '\n'.join(spans)
    return html


def set_one_week_period(driver: WebDriver) -> None:
    range_chooser = driver.find_element(By.CSS_SELECTOR, 'div.content-date')
    range_chooser.click()

    WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.options__list-content')))

    list_content_div = driver.find_element(By.CSS_SELECTOR, 'div.options__list-content')
    nested_div = list_content_div.find_element(By.ID, '7')
    nested_div.click()
    time.sleep(15)


def move_to_word_news(driver: WebDriver) -> None:
    word_button = driver.find_element(By.ID, 'global')
    word_button.click()
    time.sleep(10)


def send_mail(html_content: str) -> None:
    email_subject = 'Infopiguła news'
    yag = yagmail.SMTP(os.getenv('SRC_MAIL'), os.getenv('SRC_PWD'), port=587, smtp_starttls=True, smtp_ssl=False)
    yag.send(to=os.getenv('DST_MAIL'), subject=email_subject, contents=(html_content, 'text/html'))


def main() -> None:
    if platform.system() == "Linux":
        os.nice(10)
        
    load_dotenv()
    driver = get_driver()
    driver.maximize_window()
    url = 'https://infopigula.pl/#/'
    driver.get(url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.content-date')))

    set_one_week_period(driver)
    scroll_to_bottom(driver, num_scrolls=4)

    page = '''<!DOCTYPE html>
<html>
    <head>
      <meta charset="UTF-8">
      <title>Title of the Webpage</title>
    </head>
    <body>
        <h2>Polska</h2>\n
'''
    page += get_news(driver)

    move_to_word_news(driver)
    scroll_to_bottom(driver, num_scrolls=4)
    page += '<h2>Świat</h2>\n'
    page += get_news(driver)

    page += '''
    </body>
</html>
'''
    with open('index.html', 'wt', encoding='utf-8') as f:
        f.write(page)

    send_mail(page)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - Line: %(lineno)d - %(filename)s - %(funcName)s() - %(message)s',
        level=logging.DEBUG
    )
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    schedule.every().saturday.at("12:00").do(main)
    i = 0
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except Exception as e:
            logging.exception("An error occurred:")
            i += 1
            if i > 10:
                logging.error('Exiting program due to too many errors')
                break
    # main()
