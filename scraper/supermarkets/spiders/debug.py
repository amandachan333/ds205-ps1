
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

chrome_options = Options()
driver = webdriver.Chrome(options=chrome_options)

driver.get("https://www.waitrose.com/ecom/shop/browse/groceries/bakery")

try:
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    accept = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Accept")]'))
    )
    accept.click()
    time.sleep(2)
except:
    pass

time.sleep(3)

# Look for total product count indicator
page_text = driver.find_element(By.TAG_NAME, 'body').text

# Search for patterns like "Showing 1-50 of 500"
import re
matches = re.findall(r'(\d+)\s*(?:of|results|products|items)', page_text, re.IGNORECASE)
print("Possible total counts found:")
for match in matches:
    print(f"  {match}")

# Check if there are subcategories instead of flat list
subcategories = driver.find_elements(By.XPATH, '//a[contains(@href, "/browse/groceries/bakery/")]')
print(f"\nSubcategories found: {len(subcategories)}")
for sub in subcategories[:10]:
    print(f"  - {sub.text}: {sub.get_attribute('href')}")

# Count products
cards = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="product-pod"]')
print(f"\nProduct cards on page: {len(cards)}")

# Manually click load more and see what happens
print("\n\nMANUALLY click 'Load more' in the browser window")
print("Then tell me: Do more products appear?")
print("If yes - take a screenshot of what changed")
print("If no - maybe bakery only has 50 products or uses subcategories")

input("\nPress Enter to close...")
driver.quit()
EOF