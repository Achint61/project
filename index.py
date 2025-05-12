import time
import random
import pandas as pd
import requests
from flask import Flask, request, render_template
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# ✅ Set your chromedriver path
CHROMEDRIVER_PATH = r"C:\Users\rathi\Downloads\chromedriver-win64\chromedriver.exe"

def resolve_short_url(url):
    try:
        session = requests.Session()
        response = session.head(url, allow_redirects=True)
        return response.url if response.url.startswith("http") else url
    except:
        return url

def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return uc.Chrome(driver_executable_path=CHROMEDRIVER_PATH, options=options)

def try_click_reviews_button(driver):
    try:
        xpath = "//span/a[@jsaction='FNFY6c'][1]"
        reviews_link = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        reviews_link.click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="main"]'))
        )
        return True
    except:
        return False

def scroll_reviews(driver, max_scrolls=200):
    scrollable_xpath = '//div[@jsname="ShBeI"]/ancestor::div[@jscontroller="e6Mltb"]'
    try:
        scrollable_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, scrollable_xpath))
        )
    except:
        scrollable_div = driver.find_element(By.TAG_NAME, 'body')

    last_review_count = 0
    for _ in range(max_scrolls):
        driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", scrollable_div)
        time.sleep(random.uniform(2.0, 3.0))
        reviews_loaded = driver.find_elements(By.XPATH, '//div/div[@jsname="ShBeI"]')
        if len(reviews_loaded) == last_review_count:
            break
        last_review_count = len(reviews_loaded)

def get_star_rating(aria_label):
    try:
        rating_value = float(aria_label.strip().split()[1])
        return round(rating_value, 1)
    except:
        return "N/A"

def scrape_business_reviews(url):
    driver = init_driver()
    try:
        driver.get(url)
        time.sleep(4)

        if not try_click_reviews_button(driver):
            return pd.DataFrame()

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//div/div[@jsname="ShBeI"]'))
        )

        scroll_reviews(driver)

        review_blocks = driver.find_elements(By.XPATH, '//div/div[@jsname="ShBeI"]')
        reviews = []
        for block in review_blocks:
            try:
                # ✅ Click the "More" button if present to expand full review
                try:
                    more_button = block.find_element(By.XPATH, './/div/a[@class="MtCSLb"]')
                    driver.execute_script("arguments[0].click();", more_button)
                    time.sleep(0.2)
                except:
                    pass

                name = block.find_element(By.XPATH, './/div[@class="Vpc5Fe"]').text.strip()
                rating_div = block.find_element(By.XPATH, './/div[@class="dHX2k "]')
                rating = get_star_rating(rating_div.get_attribute("aria-label"))

                try:
                    text = block.find_element(By.CLASS_NAME, 'OA1nbd').text.strip()
                except:
                    try:
                        text = block.find_element(By.XPATH, './/span[@jscontroller]').text.strip()
                    except:
                        text = ""

                date = block.find_element(By.XPATH, './/div[@class="k0Ysuc"]/span').text.strip()

                try:
                    images_container = block.find_elements(By.XPATH, './/div[@class="Se89we"]//img')
                    img_urls = [img.get_attribute("src") for img in images_container if img.get_attribute("src")]
                    img_url = ", ".join(img_urls)
                except:
                    img_url = ""

                reviews.append({
                    "Name": name,
                    "Rating": rating,
                    "Review": text,
                    "Date": date,
                    "Image": img_url
                })
            except:
                continue

        return pd.DataFrame(reviews)

    finally:
        try:
            driver.quit()
        except:
            pass

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query")
        if not query:
            return render_template("index.html", error="Please enter a business name or URL")

        url = resolve_short_url(query) if query.startswith("http") else f"https://www.google.com/search?q={query.replace(' ', '+')}"
        df = scrape_business_reviews(url)

        if df.empty:
            return render_template("index.html", error="No reviews found or failed to extract.")

        return render_template("index.html", query=query, reviews=df.to_dict(orient="records"))

    return render_template("index.html")

if __name__ == '__main__':
    app.run()
