from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import json
import time
from datetime import datetime
from pathlib import Path
import re

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 15)

print("Loading existing product URLs from your JSON file...")

with open('scraper/data/scraped/waitrose_all_products_20260209_163435.json', 'r') as f:
    old_data = json.load(f)

product_urls = []
if 'products' in old_data:
    for p in old_data['products']:
        if p.get('url'):
            product_urls.append((p.get('product_id'), p.get('url')))
else:
    for p in old_data:
        if p.get('url'):
            product_urls.append((p.get('product_id'), p.get('url')))

print(f"Found {len(product_urls)} product URLs\n")

enriched_products = []
failed_count = 0

print("Enriching with barcodes and nutrition...\n")

for idx, (product_id, url) in enumerate(product_urls, 1):
    print(f"{idx}/{len(product_urls)}. {product_id}...", end=' ')
    
    try:
        driver.get(url)
        
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))
        time.sleep(3)
        
        script = None
        try:
            script = driver.find_element(By.ID, '__NEXT_DATA__')
        except:
            all_scripts = driver.find_elements(By.TAG_NAME, 'script')
            for s in all_scripts:
                script_id = s.get_attribute('id') or ''
                if 'next' in script_id.lower() or 'data' in script_id.lower():
                    script = s
                    break
        
        if not script:
            print("No JSON found")
            failed_count += 1
            continue
        
        json_text = script.get_attribute('innerHTML')
        if not json_text or len(json_text) < 100:
            print("Empty JSON")
            failed_count += 1
            continue
        
        data = json.loads(json_text)
        
        product_json = data.get('props', {}).get('pageProps', {}).get('product', {})
        
        if not product_json:
            print("No product data")
            failed_count += 1
            continue
        
        product_data = {
            'url': url,
            'product_id': product_json.get('lineNumber'),
            'name': product_json.get('name'),
            'price': product_json.get('displayPrice'),
            'size': product_json.get('size'),
            'brand': product_json.get('brand'),
            'category': 'bakery',
            'scraped_at': datetime.now().isoformat()
        }
        
        barcodes = product_json.get('barCodes', [])
        product_data['barcode'] = barcodes[0] if barcodes else None
        
        images = product_json.get('images', {})
        product_data['image_url'] = images.get('large') or images.get('medium')
        
        product_data['description'] = product_json.get('summary')
        
        contents = product_json.get('contents', {})
        
        ingredients_html = contents.get('ingredients', '')
        if ingredients_html:
            ingredients_clean = re.sub('<[^<]+?>', '', ingredients_html)
            ingredients_clean = re.sub(r'\s+', ' ', ingredients_clean).strip()
            ingredients_clean = re.sub(r'^INGREDIENTS:\s*', '', ingredients_clean, flags=re.IGNORECASE)
            product_data['ingredients'] = ingredients_clean if ingredients_clean else None
        else:
            product_data['ingredients'] = None
        
        nutrients = contents.get('nutrients', {})
        if nutrients and nutrients.get('nutrientsData'):
            nutrition_dict = {}
            for nutrient in nutrients['nutrientsData']:
                name = nutrient.get('name')
                value = nutrient.get('valuePerUnit')
                if name and value:
                    nutrition_dict[name] = value
            product_data['nutrition_info'] = nutrition_dict if nutrition_dict else None
        else:
            product_data['nutrition_info'] = None
        
        allergen_note = contents.get('ingredientsNote', '')
        if allergen_note:
            allergen_clean = re.sub('<[^<]+?>', '', allergen_note)
            product_data['allergens'] = allergen_clean if allergen_clean else None
        else:
            product_data['allergens'] = None
        
        product_data['product_type'] = product_json.get('productType')
        
        enriched_products.append(product_data)
        print(f"{product_data.get('name', 'Unknown')[:35]}")
        
    except Exception as e:
        print(f"Error: {str(e)[:40]}")
        failed_count += 1
    
    time.sleep(1)
    
    if idx % 50 == 0:
        print(f"\nProgress: {idx}/{len(product_urls)} | Success: {len(enriched_products)} | Failed: {failed_count}\n")

driver.quit()

output_dir = Path('data/scraped')
output_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filepath = output_dir / f'waitrose_bakery_{timestamp}.jsonl'

with open(filepath, 'w', encoding='utf-8') as f:
    for product in enriched_products:
        f.write(json.dumps(product, ensure_ascii=False) + '\n')

print("\n" + "="*60)
print(f"Enriched {len(enriched_products)} products")
print(f"Failed: {failed_count}")
print(f"Saved to: {filepath}")

with_barcode = sum(1 for p in enriched_products if p.get('barcode'))
with_ingredients = sum(1 for p in enriched_products if p.get('ingredients'))
with_nutrition = sum(1 for p in enriched_products if p.get('nutrition_info'))

print("\nData Quality:")
print(f"  With barcode: {with_barcode}/{len(enriched_products)}")
print(f"  With ingredients: {with_ingredients}/{len(enriched_products)}")
print(f"  With nutrition: {with_nutrition}/{len(enriched_products)}")
print("="*60)