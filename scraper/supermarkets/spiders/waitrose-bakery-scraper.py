"""
Waitrose Bakery Spider using Selenium
Selenium is required because product data is loaded via JavaScript (see SCRAPY_VS_SELENIUM_JUSTIFICATION.md)
"""

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


class WaitroseBakerySeleniumScraper:
    """Scraper for Waitrose bakery section using Selenium"""
    
    def __init__(self, headless=True):
        """Initialize the scraper with Chrome driver"""
        self.start_url = "https://www.waitrose.com/ecom/shop/browse/groceries/bakery"
        self.products = []
        self.seen_product_ids = set()
        
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        
        # Initialize driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
        print("✓ Chrome driver initialized")
    
    def scrape(self):
        """Main scraping method"""
        print(f"\nStarting scrape of: {self.start_url}")
        print("=" * 60)
        
        try:
            # Load the bakery page
            self.driver.get(self.start_url)
            time.sleep(3)  # Wait for JavaScript to load
            
            # Handle cookie consent if present
            try:
                cookie_accept = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="accept-all"]')
                if cookie_accept.is_displayed():
                    print("✓ Accepting cookies...")
                    cookie_accept.click()
                    time.sleep(2)
            except:
                try:
                    # Try alternative selectors
                    cookie_accept = self.driver.find_element(By.XPATH, '//button[contains(text(), "Accept")]')
                    if cookie_accept.is_displayed():
                        print("✓ Accepting cookies...")
                        cookie_accept.click()
                        time.sleep(2)
                except:
                    print("  No cookie banner found or already accepted")
            
            print("✓ Page loaded, waiting for products...")
            
            # Wait for product cards to load
            self.wait_for_products()
            
            # Get all product cards on the page
            self.scrape_current_page()
            
            # Handle load more button to get all products
            self.handle_pagination()
            
        except Exception as e:
            print(f"✗ Error during scraping: {e}")
            # Save screenshot for debugging
            try:
                screenshot_path = Path(__file__).parent / 'error_screenshot.png'
                self.driver.save_screenshot(str(screenshot_path))
                print(f"  Screenshot saved to: {screenshot_path}")
            except:
                pass
        finally:
            self.driver.quit()
            print("\n✓ Browser closed")
        
        # Save results
        self.save_data()
        
        return self.products
    
    def wait_for_products(self):
        """Wait for product elements to load"""
        try:
            # Wait for product cards (using data-testid from your screenshot)
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="product-pod"]'))
            )
            print("✓ Products loaded")
        except TimeoutException:
            print("✗ Timeout waiting for products to load")
            print("  Check if selectors need updating")
    
    def scrape_current_page(self):
        """Scrape all products on the current page"""
        # Find all product cards
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="product-pod"]')
        
        print(f"\nFound {len(product_elements)} products on page")
        
        for idx, product_elem in enumerate(product_elements, 1):
            try:
                product_data = self.extract_product_data(product_elem)
                
                # Check for duplicates
                if product_data['product_id'] not in self.seen_product_ids:
                    self.products.append(product_data)
                    self.seen_product_ids.add(product_data['product_id'])
                    print(f"  {len(self.products)}. {product_data['name']}")
                
            except Exception as e:
                print(f"  ✗ Error extracting product {idx}: {e}")
        
        time.sleep(2) 
    
    def extract_product_data(self, element):
        """Extract data from a single product element"""
        
        # Product ID
        product_id = element.get_attribute('data-product-id')
        
        # Product name
        name_elem = element.find_element(By.CSS_SELECTOR, 'span[class*="name"]')
        name = name_elem.text
        
        # Product link
        link_elem = element.find_element(By.CSS_SELECTOR, 'a[href*="/products/"]')
        url = link_elem.get_attribute('href')
        
        # Price - try multiple selectors
        price = None
        try:
            price_elem = element.find_element(By.CSS_SELECTOR, 'span[class*="price"]')
            price = price_elem.text
        except NoSuchElementException:
            pass
        
        # Size/weight
        size = None
        try:
            size_elem = element.find_element(By.CSS_SELECTOR, 'span[class*="size"]')
            size = size_elem.text
        except NoSuchElementException:
            pass
        
        # Image URL
        image_url = None
        try:
            img_elem = element.find_element(By.CSS_SELECTOR, 'img')
            image_url = img_elem.get_attribute('src')
        except NoSuchElementException:
            pass
        
        # Availability
        availability = element.get_attribute('data-product-availability')
        
        return {
            'product_id': product_id,
            'name': name,
            'url': url,
            'price': price,
            'size': size,
            'image_url': image_url,
            'availability': availability,
            'category': 'bakery',
            'scraped_at': datetime.now().isoformat()
        }
    
    def handle_pagination(self):
        """Handle 'load more' button to load all products"""
        load_count = 0
        max_attempts = 100  # Safety limit to prevent infinite loops
        
        # Scroll to bottom to reveal load more button
        print("\n--- Looking for 'Load more' button ---")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        while load_count < max_attempts:
            try:
                # Look for "load more" button - try multiple possible selectors
                load_more_button = None
                selectors = [
                    'button[data-testid="load-more"]',
                    'button[class*="load-more"]',
                    'button[class*="show-more"]',
                    'button[class*="loadMore"]',
                    'button[class*="showMore"]',
                    '//button[contains(text(), "Load more")]',
                    '//button[contains(text(), "Show more")]',
                    '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "load")]',
                    '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "show")]'
                ]
                
                # Try CSS selectors first
                for selector in selectors[:5]:
                    try:
                        load_more_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if load_more_button.is_displayed() and load_more_button.is_enabled():
                            break
                        else:
                            load_more_button = None
                    except (NoSuchElementException, Exception):
                        continue
                
                # Try XPath selectors if CSS didn't work
                if not load_more_button:
                    for xpath in selectors[5:]:
                        try:
                            load_more_button = self.driver.find_element(By.XPATH, xpath)
                            if load_more_button.is_displayed() and load_more_button.is_enabled():
                                break
                            else:
                                load_more_button = None
                        except (NoSuchElementException, Exception):
                            continue
                
                # If no button found or not visible/enabled, we're done
                if not load_more_button:
                    print(f"\n✓ No more items to load (clicked 'Load more' {load_count} times)")
                    break
                
                # Click the load more button
                print(f"\n→ Clicking 'Load more' button (attempt {load_count + 1})...")
                
                # Scroll to button before clicking
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(1)
                
                # Use JavaScript click to avoid interception issues
                try:
                    self.driver.execute_script("arguments[0].click();", load_more_button)
                    print(f"  ✓ Button clicked successfully")
                except Exception as click_error:
                    # If JavaScript click fails, try regular click
                    try:
                        load_more_button.click()
                        print(f"  ✓ Button clicked successfully")
                    except:
                        print(f"  ✗ Failed to click button: {click_error}")
                        break
                
                load_count += 1
                
                # Wait for new products to load
                print(f"  Waiting for new products to load...")
                time.sleep(4)
                
                # Track products before scraping
                products_before = len(self.products)
                
                # Scroll back to top to see new products
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
                # Scrape newly loaded products
                self.scrape_current_page()
                
                # Check if we actually got new products
                products_after = len(self.products)
                new_products = products_after - products_before
                print(f"  Added {new_products} new products (total: {products_after})")
                
                # If no new products were added, we're done
                if new_products == 0:
                    print(f"\n✓ No new products after clicking (total: {products_after})")
                    break
                
                # Scroll back to bottom for next iteration
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
            except NoSuchElementException:
                print(f"\n✓ All products loaded (clicked 'Load more' {load_count} times)")
                break
            except Exception as e:
                print(f"\n✗ Error while loading more products: {e}")
                print(f"   Completed {load_count} load attempts")
                break
    
    def save_data(self):
        """Save scraped data to JSON file"""
        # Create output directory
        output_dir = Path(__file__).parent.parent.parent / 'data' / 'scraped'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'waitrose_bakery_selenium_{timestamp}.json'
        filepath = output_dir / filename
        
        # Save to JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.products, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'=' * 60}")
        print(f"✓ Scraped {len(self.products)} products")
        print(f"✓ Data saved to: {filepath}")
        print(f"{'=' * 60}")


def main():
    """Main entry point"""
    scraper = WaitroseBakerySeleniumScraper(headless=False)  # Set True for headless
    products = scraper.scrape()
    return products


if __name__ == "__main__":
    main()
