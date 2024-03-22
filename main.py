import logging
import time

import schedule as schedule
import yagmail as yagmail
import yaml
from bs4 import BeautifulSoup
from easydict import EasyDict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def scroll_to_bottom(driver: WebDriver, num_scrolls: int) -> None:
    for _ in range(num_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)


def get_driver() -> webdriver.Chrome:
    op = webdriver.ChromeOptions()
    op.add_argument('--headless')
    op.add_argument("window-size=1920,1080")  # Specify resolution
    # options.add_argument("--no-sandbox")
    # options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--disable-gpu")

    # Define a user agent
    op.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/2b7c7"
    )
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=op)


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
    with open('secrets.yml', 'rt') as f:
        secrets = EasyDict(yaml.safe_load(f))
    yag = yagmail.SMTP(secrets.src_mail, secrets.src_pwd, port=587, smtp_starttls=True, smtp_ssl=False)
    yag.send(to=secrets.dst_mail, subject=email_subject, contents=(html_content, 'text/html'))


def main() -> None:
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
    logging.basicConfig(filename='error.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        schedule.every().saturday.at("12:00").do(main)
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logging.exception("An error occurred:")
        raise
    # main()
