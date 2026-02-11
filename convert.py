import json

# Read from actual location
with open('scraper/data/scraped/waitrose_all_products_20260209_163435.json', 'r') as f:
    data = json.load(f)

# Write to project-level data/scraped/
import os
os.makedirs('data/scraped', exist_ok=True)

with open('data/scraped/waitrose_bakery.jsonl', 'w') as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f'â Converted {len(data)} products')
print('â Saved to: data/scraped/waitrose_bakery.jsonl')
