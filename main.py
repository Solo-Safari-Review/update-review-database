from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
import time, mysql.connector
from datetime import datetime
from prep_func import *
from save import to_db
from preprocessing import preprocessing
from get_attributes import *
from scrapping_function import *
import json

# Initialize WebDriver
options = webdriver.ChromeOptions()
# options.add_argument("--headless=new")  # Run without open the browser
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
query = "SELECT * FROM reviews ORDER BY id DESC LIMIT 1"
cursor.execute(query)
last_data = cursor.fetchone()

if last_data:
    target_timestamp = last_data['created_at'].replace(minute=0, second=0, microsecond=0)
    last_username = last_data['username']
else:
    # manual timestamp
    target_timestamp = time_to_timestamp("1 hari lalu")
    last_username = ""

before_timestamp = datetime.now()
on_target = False

cursor.close()
conn.close()

# get the frame element
frame = driver.find_element(By.CLASS_NAME, "DxyBCb")
scroll_origin = ScrollOrigin.from_element(frame, 0, 0)
target_found = False

# Get the reviews
while not on_target:

    # scroll review
    while not target_found:
        ActionChains(driver)\
        .scroll_from_origin(scroll_origin, 0, 1500)\
        .perform()

        times = time_to_timestamp(driver.find_elements(By.CLASS_NAME, "rsqaWe"))
        if any(time < target_timestamp for time in times): target_found = True

    reviews = driver.find_elements(By.CLASS_NAME, "jJc9Ad")

    data_reviews = []
    for review in reviews:
            # get time
            try:
                time = getTime(review)
            except Exception as e:
                print(f"Error time: {e}")

            if time >= before_timestamp: continue
            if time < target_timestamp: on_target = True; break

            # get review text
            try:
                content = getReviewText(review)
                raw_content = content
            except Exception as e:
                print(f"Error content: {e}")

            if content is None: continue

            # get username
            try:
                username = getUsername(review)
            except Exception as e:
                print(f"Error username: {e}")

            # get local guide, total reviews
            try:
                is_local_guide, reviewer_number_of_reviews = getSubUserInfo(review)
            except Exception as e:
                print(f"Error sub_user_info: {e}")

            # get rating
            try:
                rating = getRating(review)
            except Exception as e:
                print(f"Error rating: {e}")

            # get likes
            try:
                likes = getLikes(review)
            except Exception as e:
                print(f"Error likes: {e}")

            # get images
            try:
                image_count = getImageCount(review)
            except Exception as e:
                print(f"Error image_count: {e}")

            # get review context
            try:
                review_context_1, review_context_2, review_context_3, review_context_4 = getReviewContexts(review)
            except Exception as e:
                print(f"Error review_contexts: {e}")

            # get answer
            try:
                answer = getAnswer(review)
            except Exception as e:
                print(f"Error answer: {e}")

            # get is_extreme_review
            try:
                is_extreme_review = getIsExtremeReview(rating)
            except Exception as e:
                print(f"Error is_extreme_review: {e}")

            data_reviews.append({
                "username": username,
                "time": time,
                "rating": rating,
                "content": content,
                "likes": likes,
                "review_context_1": review_context_1,
                "review_context_2": review_context_2,
                "review_context_3": review_context_3,
                "review_context_4": review_context_4,
                "answer": answer,
                "is_local_guide": is_local_guide,
                "reviewer_number_of_reviews": reviewer_number_of_reviews,
                "image_count": image_count,
                "is_extreme_review": is_extreme_review,
                "raw_content": raw_content
            })

driver.quit()

# Clean data
data_reviews.reverse()

# clean member
data_reviews_after = []
have_last_username = False

for data in data_reviews:
    if data["username"] == last_username:
        have_last_username = True
        continue

    if have_last_username is True:
        data_reviews_after.append(data)

if have_last_username is True:
    data_reviews = data_reviews_after

# preprocessing & get attributes
for item in data_reviews:
    item['content'] = preprocessing(item['content'])
    item['answered_any_review_context'] = answer_context(item['review_context_1'], item['review_context_2'], item['review_context_3'], item['review_context_4'])
    item['contains_question'] = contains_question(item['content'])
    item['contains_number'] = contains_number(item['content'])
    item['review_length'] = get_length(item['content'])
    item['is_weekend'] = is_weekend(item['time'])

if data_reviews: # Ensure data_reviews is not empty before trying to dump
    try:
        json_output = json.dumps(data_reviews, default=json_datetime_converter, indent=4) # indent for pretty print, optional
        print(json_output)

        if json_output:
            # save to database
            to_db(data_reviews)

    except TypeError as e:
        # Fallback or error representation if serialization fails for an unexpected reason
        error_json = json.dumps({"error": "Failed to serialize data_reviews to JSON", "details": str(e)})
        print(error_json)
elif not data_reviews and 'target_timestamp' in locals(): # If no new reviews were fetched
    print(json.dumps([])) # Print an empty JSON array
else: # If data_reviews was never populated or an earlier critical error occurred
    print(json.dumps({"error": "No data was processed or an early error occurred."}))
