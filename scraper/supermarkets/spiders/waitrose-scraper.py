from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import time
from datetime import datetime
from pathlib import Path
import re
from typing import List, Dict, Optional


class WaitroseScraper:
    """Enhanced scraper for Waitrose groceries with NOVA classification support"""
    
    # Non-food categories to exclude
    NON_FOOD_CATEGORIES = {
        'household', 'toiletries', 'health', 'beauty', 'baby', 'toddler', 
        'pet', 'valentine', 'occasion', 'brands', 'easter', 'pancake'
    }
    
    # Common Waitrose brands for extraction
    KNOWN_BRANDS = [
        'Waitrose', 'Essential Waitrose', 'Duchy Organic', 'Waitrose 1',
        'Waitrose & Partners', 'Cooks\' Ingredients', 'LoveLife'
    ]
    
    def __init__(self, headless=True, max_categories=None):
        """
        Initialize the scraper
        
        Args:
            headless: Run browser in headless mode
            max_categories: Limit number of categories to scrape (None = all)
        """
        self.base_url = "https://www.waitrose.com"
        self.groceries_url = f"{self.base_url}/ecom/shop/browse/groceries"
        self.max_categories = max_categories
        
        self.categories = []
        self.all_products = []
        self.seen_product_ids = set()
        
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        
        # Initialize driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
        print("â Chrome driver initialized")
    
    def scrape_all(self):
        """Main scraping workflow"""
        print(f"\n{'='*70}")
        print("WAITROSE GROCERY SCRAPER - NOVA Classification Analysis")
        print(f"{'='*70}\n")
        
        try:
            # Step 1: Discover food categories
            self.discover_food_categories()
            
            # Step 2: Scrape each category
            categories_to_scrape = self.categories[:self.max_categories] if self.max_categories else self.categories
            
            for idx, category in enumerate(categories_to_scrape, 1):
                print(f"\n[{idx}/{len(categories_to_scrape)}] Scraping: {category['name']}")
                print("-" * 70)
                self.scrape_category(category)
                time.sleep(3)  # Be polite between categories
            
            # Step 3: Save all data
            self.save_all_data()
            
        except Exception as e:
            print(f"\nâ Fatal error: {e}")
            self.save_screenshot('fatal_error.png')
        finally:
            self.driver.quit()
            print("\nâ Browser closed")
        
        return self.all_products
    
    def discover_food_categories(self):
        """Discover all food categories from the groceries page"""
        print(f"Discovering categories from: {self.groceries_url}")
        
        try:
            self.driver.get(self.groceries_url)
            time.sleep(3)
            
            # Handle cookie consent
            self.handle_cookies()
            
            # Wait for category elements to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/browse/groceries/"]'))
            )
            
            # Find all category links
            category_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'a[href*="/browse/groceries/"]'
            )
            
            # Extract unique categories
            seen_urls = set()
            for elem in category_elements:
                try:
                    url = elem.get_attribute('href')
                    name = elem.text.strip()
                    
                    # Skip if empty, already seen, or is the groceries home
                    if not name or url in seen_urls or url == self.groceries_url:
                        continue
                    
                    # Check if it's a food category (exclude household, pet, etc.)
                    if self.is_food_category(name, url):
                        category_slug = url.split('/')[-1]
                        self.categories.append({
                            'name': name,
                            'url': url,
                            'slug': category_slug
                        })
                        seen_urls.add(url)
                        
                except Exception as e:
                    continue
            
            print(f"â Found {len(self.categories)} food categories:")
            for cat in self.categories:
                print(f"  - {cat['name']}")
            
            # Save categories list
            self.save_categories()
            
        except Exception as e:
            print(f"â Error discovering categories: {e}")
            self.categories = [{'name': 'Bakery', 'url': f'{self.base_url}/ecom/shop/browse/groceries/bakery', 'slug': 'bakery'}]
    
    def is_food_category(self, name: str, url: str) -> bool:
        """Determine if a category is food-related"""
        name_lower = name.lower()
        url_lower = url.lower()
        
        # Check against non-food keywords
        for non_food in self.NON_FOOD_CATEGORIES:
            if non_food in name_lower or non_food in url_lower:
                return False
        
        return True
    
    def scrape_category(self, category: Dict):
        """Scrape all products from a single category"""
        try:
            self.driver.get(category['url'])
            time.sleep(3)
            
            # Wait for products to load
            self.wait_for_products()
            
            # Scrape initial page
            self.scrape_current_page(category['slug'])
            
            # Handle pagination
            self.handle_pagination(category['slug'])
            
        except Exception as e:
            print(f"â Error scraping {category['name']}: {e}")
            self.save_screenshot(f"error_{category['slug']}.png")
    
    def wait_for_products(self):
        """Wait for product elements to load"""
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="product-pod"]'))
            )
            print("â Products loaded")
        except TimeoutException:
            print("â Timeout waiting for products")
    
    def scrape_current_page(self, category_slug: str):
        """Scrape all products visible on current page"""
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="product-pod"]')
        
        print(f"  Found {len(product_elements)} products on page")
        
        for idx, product_elem in enumerate(product_elements, 1):
            try:
                product_data = self.extract_product_card_data(product_elem, category_slug)
                
                # Check for duplicates
                if product_data['product_id'] not in self.seen_product_ids:
                    self.all_products.append(product_data)
                    self.seen_product_ids.add(product_data['product_id'])
                    print(f"    {len(self.all_products)}. {product_data['name'][:60]}")
                
            except Exception as e:
                print(f"    â Error extracting product {idx}: {e}")
        
        time.sleep(2)
    
    def extract_product_card_data(self, element, category_slug: str) -> Dict:
        """Extract data from a product card element"""
        
        # Product ID
        product_id = element.get_attribute('data-product-id')
        
        # Product name
        name_elem = element.find_element(By.CSS_SELECTOR, 'span[class*="name"]')
        name = name_elem.text
        
        # Product URL
        link_elem = element.find_element(By.CSS_SELECTOR, 'a[href*="/products/"]')
        relative_url = link_elem.get_attribute('href')
        url = relative_url if relative_url.startswith('http') else f"{self.base_url}{relative_url}"
        
        # Price
        price = self.safe_extract(element, 'span[class*="price"]')
        
        # Size/weight
        size = self.safe_extract(element, 'span[class*="size"]')
        
        # Image URL
        image_url = None
        try:
            img_elem = element.find_element(By.CSS_SELECTOR, 'img')
            image_url = img_elem.get_attribute('src')
        except NoSuchElementException:
            pass
        
        # Availability
        availability = element.get_attribute('data-product-availability')
        
        # Extract brand from name
        brand = self.extract_brand(name)
        
        # Build basic product data
        product_data = {
            'product_id': product_id,
            'name': name,
            'brand': brand,
            'url': url,
            'price': price,
            'size': size,
            'image_url': image_url,
            'availability': availability,
            'category': category_slug,
            'scraped_at': datetime.now().isoformat(),
            # Fields to be enriched from product page
            'barcode': None,
            'ingredients': None,
            'nutrition_info': None,
            'product_type': None
        }
        
        return product_data
    
    def extract_brand(self, name: str) -> Optional[str]:
        """Extract brand from product name"""
        if not name:
            return None
        
        # Check known brands first
        for brand in self.KNOWN_BRANDS:
            if name.startswith(brand):
                return brand
        
        # Otherwise, take first word as potential brand
        first_word = name.split()[0] if name else None
        return first_word
    
    def scrape_product_details(self, product_url: str) -> Dict:
        """
        Visit product detail page to extract additional information
        
        Note: This is optional and can be enabled for deeper analysis
        WARNING: This significantly increases scraping time
        """
        details = {
            'barcode': None,
            'ingredients': None,
            'nutrition_info': None,
            'product_type': None
        }
        
        try:
            self.driver.get(product_url)
            time.sleep(2)
            
            # Try to find barcode/EAN
            # Common locations: data attributes, meta tags, or visible on page
            try:
                # Check data attributes
                barcode = self.driver.find_element(By.CSS_SELECTOR, '[data-product-ean]')
                details['barcode'] = barcode.get_attribute('data-product-ean')
            except NoSuchElementException:
                # Try to find in text
                page_text = self.driver.find_element(By.TAG_NAME, 'body').text
                ean_match = re.search(r'EAN[:\s]*(\d{13})', page_text, re.IGNORECASE)
                if ean_match:
                    details['barcode'] = ean_match.group(1)
            
            # Try to find ingredients
            try:
                ingredients_elem = self.driver.find_element(
                    By.XPATH, 
                    '//*[contains(text(), "Ingredients") or contains(text(), "INGREDIENTS")]'
                )
                details['ingredients'] = ingredients_elem.text
            except NoSuchElementException:
                pass
            
            # Try to find nutrition info
            try:
                nutrition_elem = self.driver.find_element(
                    By.CSS_SELECTOR,
                    '[class*="nutrition"]'
                )
                details['nutrition_info'] = nutrition_elem.text
            except NoSuchElementException:
                pass
            
        except Exception as e:
            print(f"      â  Could not scrape details: {e}")
        
        return details
    
    def handle_pagination(self, category_slug: str):
        """Handle 'load more' button pagination"""
        load_count = 0
        max_attempts = 100
        
        print("\n  Looking for 'Load more' button...")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        while load_count < max_attempts:
            try:
                load_more_button = self.find_load_more_button()
                
                if not load_more_button:
                    print(f"  â No more items to load (clicked {load_count} times)")
                    break
                
                print(f"  â Clicking 'Load more' (attempt {load_count + 1})...")
                
                # Scroll to button
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(1)
                
                # Click using JavaScript
                self.driver.execute_script("arguments[0].click();", load_more_button)
                load_count += 1
                
                # Wait for new products
                time.sleep(4)
                
                # Track new products
                products_before = len(self.all_products)
                
                # Scroll to top and scrape
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                self.scrape_current_page(category_slug)
                
                new_products = len(self.all_products) - products_before
                print(f"    Added {new_products} new products (total: {len(self.all_products)})")
                
                if new_products == 0:
                    print(f"  â No new products loaded")
                    break
                
                # Scroll back to bottom
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
            except Exception as e:
                print(f"  â Error during pagination: {e}")
                break
    
    def find_load_more_button(self):
        """Find the load more button using multiple strategies"""
        selectors = [
            'button[data-testid="load-more"]',
            'button[class*="load-more"]',
            'button[class*="show-more"]',
            '//button[contains(translate(., "LOAD", "load"), "load more")]',
            '//button[contains(translate(., "SHOW", "show"), "show more")]',
        ]
        
        # Try CSS selectors
        for selector in selectors[:3]:
            try:
                button = self.driver.find_element(By.CSS_SELECTOR, selector)
                if button.is_displayed() and button.is_enabled():
                    return button
            except NoSuchElementException:
                continue
        
        # Try XPath selectors
        for xpath in selectors[3:]:
            try:
                button = self.driver.find_element(By.XPATH, xpath)
                if button.is_displayed() and button.is_enabled():
                    return button
            except NoSuchElementException:
                continue
        
        return None
    
    def handle_cookies(self):
        """Accept cookie consent if present"""
        try:
            cookie_accept = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="accept-all"]')
            if cookie_accept.is_displayed():
                print("â Accepting cookies...")
                cookie_accept.click()
                time.sleep(2)
        except:
            try:
                cookie_accept = self.driver.find_element(By.XPATH, '//button[contains(text(), "Accept")]')
                if cookie_accept.is_displayed():
                    print("â Accepting cookies...")
                    cookie_accept.click()
                    time.sleep(2)
            except:
                pass
    
    def safe_extract(self, element, selector: str) -> Optional[str]:
        """Safely extract text from an element"""
        try:
            elem = element.find_element(By.CSS_SELECTOR, selector)
            return elem.text
        except NoSuchElementException:
            return None
    
    def save_categories(self):
        """Save discovered categories to JSON"""
        output_dir = Path(__file__).parent / 'data' / 'scraped'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / 'categories.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'discovered_at': datetime.now().isoformat(),
                'total_categories': len(self.categories),
                'categories': self.categories
            }, f, indent=2, ensure_ascii=False)
        
        print(f"â Categories saved to: {filepath}")
    
    def save_all_data(self):
        """Save all scraped data"""
        output_dir = Path(__file__).parent / 'data' / 'scraped'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save combined file
        combined_file = output_dir / f'waitrose_all_products_{timestamp}.json'
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump({
                'scraped_at': datetime.now().isoformat(),
                'total_products': len(self.all_products),
                'total_categories': len(self.categories),
                'categories_scraped': [cat['name'] for cat in self.categories[:self.max_categories]] if self.max_categories else [cat['name'] for cat in self.categories],
                'products': self.all_products
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*70}")
        print(f"â Scraped {len(self.all_products)} products from {len(set(p['category'] for p in self.all_products))} categories")
        print(f"â Data saved to: {combined_file}")
        
        # Also save per-category files
        self.save_by_category(output_dir, timestamp)
        
        # Print summary
        self.print_summary()
        
        print(f"{'='*70}")
    
    def save_by_category(self, output_dir: Path, timestamp: str):
        """Save products organized by category"""
        # Group products by category
        by_category = {}
        for product in self.all_products:
            cat = product['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(product)
        
        # Save each category
        category_dir = output_dir / 'by_category'
        category_dir.mkdir(exist_ok=True)
        
        for category, products in by_category.items():
            filepath = category_dir / f'{category}_{timestamp}.json'
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'product_count': len(products),
                    'products': products
                }, f, indent=2, ensure_ascii=False)
        
        print(f"â Per-category files saved to: {category_dir}")
    
    def print_summary(self):
        """Print scraping summary statistics"""
        print("\n--- Scraping Summary ---")
        
        # Products per category
        by_category = {}
        for product in self.all_products:
            cat = product['category']
            by_category[cat] = by_category.get(cat, 0) + 1
        
        print("\nProducts per category:")
        for category, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            print(f"  {category}: {count}")
        
        # Brand distribution
        brands = {}
        for product in self.all_products:
            brand = product.get('brand', 'Unknown')
            brands[brand] = brands.get(brand, 0) + 1
        
        print(f"\nTop 10 brands:")
        for brand, count in sorted(brands.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {brand}: {count}")
        
        # Data completeness
        with_price = sum(1 for p in self.all_products if p.get('price'))
        with_size = sum(1 for p in self.all_products if p.get('size'))
        with_image = sum(1 for p in self.all_products if p.get('image_url'))
        
        print(f"\nData completeness:")
        print(f"  Products with price: {with_price}/{len(self.all_products)} ({with_price/len(self.all_products)*100:.1f}%)")
        print(f"  Products with size: {with_size}/{len(self.all_products)} ({with_size/len(self.all_products)*100:.1f}%)")
        print(f"  Products with image: {with_image}/{len(self.all_products)} ({with_image/len(self.all_products)*100:.1f}%)")
    
    def save_screenshot(self, filename: str):
        """Save screenshot for debugging"""
        try:
            screenshot_path = Path(__file__).parent / filename
            self.driver.save_screenshot(str(screenshot_path))
            print(f"  Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"  Could not save screenshot: {e}")


def main():
    """Main entry point"""
    print("\nWaitrose Grocery Scraper")
    print("=" * 70)
    print("\nConfiguration:")
    print("  Headless mode: False (set to True for production)")
    print("  Max categories: 2 (set to None for all categories)")
    print("  Detail scraping: Disabled (enable scrape_product_details for barcodes)\n")
    
    # Initialize scraper
    # For testing: scrape only 2 categories
    # For production: set max_categories=None to scrape all
    scraper = WaitroseScraper(headless=False, max_categories=2)
    
    # Run scraper
    products = scraper.scrape_all()
    
    print(f"\nâ Scraping complete! Collected {len(products)} products.")
    
    return products


if __name__ == "__main__":
    main()