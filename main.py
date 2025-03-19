from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
import time, re, mysql.connector
from datetime import datetime, timedelta
from prep_func import time_to_timestamp, stars_to_int, likes_to_int
from save import to_csv, to_db

# Initialize WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run without open the browser
driver = webdriver.Chrome(options=options)

# URL Google Maps
maps_url = f"https://www.google.com/maps/search/solo+safari/"

driver.get(maps_url)

try:
    # click sorting button
    sorting_button = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-value='Urutkan']"))
    )
    sorting_button.click()

    # wait for the sorting menu
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[id='action-menu']"))
    )
    menu_button = driver.find_element(By.CSS_SELECTOR, "[id='action-menu']")

    # click newest button
    newest_button = menu_button.find_element(By.CSS_SELECTOR, "[data-index='1']")
    newest_button.click()
except Exception as e:
    print(f"Error: {e}")

# wait for the reviews fully loaded
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "jJc9Ad"))
)

# Target timestamp

# with last data from database
conn = mysql.connector.connect(
    host="localhost",
    database="solo-safari-review",
    user="root",
    password="",  # Sesuaikan dengan password Anda
)
cursor = conn.cursor(dictionary=True)
query = "SELECT * FROM reviews ORDER BY created_at DESC LIMIT 1"
cursor.execute(query)
last_data = cursor.fetchone()

target_timestamp = last_data['created_at']

cursor.close()
conn.close()

# target_timestamp = time_to_timestamp("sebulan lalu")
before_timestamp = (datetime.now() + timedelta(days=1))
on_target = False

# get the frame element
frame = driver.find_element(By.CLASS_NAME, "DxyBCb")
scroll_origin = ScrollOrigin.from_element(frame, 0, 0)
target_found = False

# Get the reviews
while not on_target:
    while not target_found:
        ActionChains(driver)\
        .scroll_from_origin(scroll_origin, 0, 1500)\
        .perform()

        times = time_to_timestamp(driver.find_elements(By.CLASS_NAME, "rsqaWe"))
        if any(time < target_timestamp for time in times): target_found = True

    reviews = driver.find_elements(By.CLASS_NAME, "jJc9Ad")

    data_reviews = []
    for review in reviews:
        try:
            time = time_to_timestamp(review.find_element(By.CLASS_NAME, "rsqaWe").text)
            if time >= before_timestamp: continue
            if time < target_timestamp: on_target = True; break

            username = review.find_element(By.CLASS_NAME, "d4r55").text
            rating = stars_to_int(review.find_element(By.CLASS_NAME, "kvMYJc").get_attribute("aria-label"))
            likes = likes_to_int(review.find_elements(By.CLASS_NAME, "pkWtMe"))

            expand_button = review.find_elements(By.CSS_SELECTOR, "[aria-label='Lihat lainnya']")
            expand_button[0].click() if expand_button else None

            # content_element = review.find_elements(By.CLASS_NAME, "wiI7pd")
            content_element = review.find_elements(By.CLASS_NAME, "MyEned")

            content = content_element[0].find_element(By.CLASS_NAME, "wiI7pd").text if content_element else "Tidak ada komentar"

            if content == "Tidak ada komentar": continue

            review_contexts_elements = review.find_elements(By.CLASS_NAME, "RfDO5c")

            review_context_1 = None
            review_context_2 = None
            review_context_3 = None
            review_context_4 = None
            if review_contexts_elements:
                idx = 0

                for review_context in review_contexts_elements:
                    if review_contexts_elements[idx].text == "Waktu kunjungan":
                        review_context_1 = review_contexts_elements[idx + 1].text
                    elif review_contexts_elements[idx].text == "Waktu antrean":
                        review_context_2 = review_contexts_elements[idx + 1].text
                    elif review_contexts_elements[idx].text == "Sebaiknya buat reservasi":
                        review_context_3 = review_contexts_elements[idx + 1].text
                    elif review_contexts_elements[idx].text == "Tempat parkir":
                        review_context_4 = review_contexts_elements[idx + 1].text

                    idx += 1

            data_reviews.append({
                "username": username,
                "time": time,
                "rating": rating,
                "content": content,
                "likes": likes,
                "review_context_1": review_context_1,
                "review_context_2": review_context_2,
                "review_context_3": review_context_3,
                "review_context_4": review_context_4
            })

        except Exception as e:
            print(f"Error: {e}")
            continue

driver.quit()

# Clean data
pattern = '[^a-zA-Z0-9.]'
replacement = ' '

data_reviews.reverse()
for data in data_reviews:
    data["content"] = re.sub(pattern, replacement, data["content"])
    data["content"] = data["content"].strip()
    data["content"] = re.sub(r"\s{2,}", ' ', data['content'])

print("Total review yang didapat: ", len(data_reviews))

# save to csv
# to_csv(data_reviews)

# save to database
to_db(data_reviews)
