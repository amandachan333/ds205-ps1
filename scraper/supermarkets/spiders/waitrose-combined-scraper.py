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
from typing import Dict, Optional


class WaitroseScraper:
    """Scraper for Waitrose groceries — collects product URLs from category
    pages then enriches each product via the __NEXT_DATA__ JSON embedded in
    individual product pages."""

    # Actual food categories on the Waitrose groceries page
    FOOD_CATEGORY_SLUGS = {
        'fresh_and_chilled', 'bakery', 'food_cupboard', 'frozen',
        'beer_wine_and_spirits', 'tea_coffee_and_soft_drinks',
    }

    BASE_URL = "https://www.waitrose.com"
    GROCERIES_URL = f"{BASE_URL}/ecom/shop/browse/groceries"

    def __init__(self, headless=True, max_categories=None):
        self.max_categories = max_categories
        self.categories = []
        self.all_products = []
        self.seen_product_ids = set()

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36"
        )

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)
        print("✓ Chrome driver initialized")

    # ------------------------------------------------------------------
    # Main workflow
    # ------------------------------------------------------------------

    def scrape_all(self):
        """Discover categories → collect product URLs → enrich each product."""
        print(f"\n{'='*60}")
        print("WAITROSE GROCERY SCRAPER")
        print(f"{'='*60}\n")

        try:
            self.discover_food_categories()

            targets = (
                self.categories[:self.max_categories]
                if self.max_categories else self.categories
            )

            # Phase 1: collect product URLs + basic category slug from listing pages
            product_stubs = []
            for idx, cat in enumerate(targets, 1):
                print(f"\n[{idx}/{len(targets)}] Listing: {cat['name']}")
                print("-" * 60)
                stubs = self.collect_product_urls(cat)
                product_stubs.extend(stubs)
                time.sleep(3)

            print(f"\n✓ Collected {len(product_stubs)} unique product URLs")

            # Phase 2: visit each product page and extract data from __NEXT_DATA__
            # Open output file now so each product is saved immediately
            output_dir = Path(__file__).parent.parent.parent.parent / 'data' / 'scraped'
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.output_path = output_dir / f'waitrose_products_{ts}.jsonl'

            print(f"\nEnriching products from detail pages...")
            print(f"Writing to: {self.output_path}\n")
            failed = 0

            with open(self.output_path, 'w', encoding='utf-8') as f:
                for idx, stub in enumerate(product_stubs, 1):
                    print(f"  {idx}/{len(product_stubs)}.", end=" ")
                    product = self.enrich_product(stub)
                    if product:
                        f.write(json.dumps(product, ensure_ascii=False) + '\n')
                        f.flush()
                        self.all_products.append(product)
                        print(product['name'][:50])
                    else:
                        failed += 1
                        print("FAILED")
                    time.sleep(1)

                    if idx % 50 == 0:
                        print(
                            f"\n  Progress: {idx}/{len(product_stubs)} | "
                            f"Success: {len(self.all_products)} | Failed: {failed}\n"
                        )

            self.print_summary()

        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
        finally:
            self.driver.quit()
            print("\n✓ Browser closed")

        return self.all_products

    # ------------------------------------------------------------------
    # Category discovery
    # ------------------------------------------------------------------

    def discover_food_categories(self):
        """Navigate to the groceries page and discover food category links."""
        print(f"Discovering categories from: {self.GROCERIES_URL}")
        try:
            self.driver.get(self.GROCERIES_URL)
            time.sleep(3)
            self.handle_cookies()

            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'a[href*="/browse/groceries/"]')
                )
            )

            seen_urls = set()
            for elem in self.driver.find_elements(
                By.CSS_SELECTOR, 'a[href*="/browse/groceries/"]'
            ):
                try:
                    url = elem.get_attribute('href')
                    name = elem.text.strip()
                    if (
                        not name
                        or url in seen_urls
                        or url == self.GROCERIES_URL
                        or not self._is_food(name, url)
                    ):
                        continue
                    self.categories.append({
                        'name': name,
                        'url': url,
                        'slug': url.split('/')[-1],
                    })
                    seen_urls.add(url)
                except NoSuchElementException:
                    continue

            print(f"✓ Found {len(self.categories)} food categories:")
            for c in self.categories:
                print(f"  - {c['name']}")

        except (TimeoutException, Exception) as e:
            print(f"✗ Error discovering categories: {e}")
            self.categories = [{
                'name': 'Bakery',
                'url': f'{self.BASE_URL}/ecom/shop/browse/groceries/bakery',
                'slug': 'bakery',
            }]

    def _is_food(self, name: str, url: str) -> bool:
        slug = url.rstrip('/').split('/')[-1]
        return slug in self.FOOD_CATEGORY_SLUGS

    # ------------------------------------------------------------------
    # Phase 1: collect product URLs from category listing pages
    # ------------------------------------------------------------------

    def collect_product_urls(self, category: Dict) -> list:
        """Load a category page and return product stubs.
        Always checks for subcategory links first — if they exist, drill
        into each one (handles hybrid pages like bakery that show some
        products AND have subcategory navigation). Falls back to
        paginating the current page only if no subcategories are found."""
        stubs = []
        try:
            self.driver.get(category['url'])
            time.sleep(3)

            # Always check for subcategories first
            subcats = self._discover_subcategories(category['url'])

            if subcats:
                print(f"  → Found {len(subcats)} subcategories, drilling in...")
                for sub in subcats:
                    print(f"    ↳ {sub['name']}")
                    stubs.extend(self.collect_product_urls(sub))
                    time.sleep(2)
            else:
                # Leaf category — scrape products and paginate
                self._wait_for_products()
                stubs.extend(self._extract_stubs(category['slug']))
                stubs.extend(self._paginate_and_collect(category['slug']))

        except Exception as e:
            print(f"  ✗ Error listing {category['name']}: {e}")
        return stubs

    def _discover_subcategories(self, parent_url: str) -> list:
        """Find child category links on a subcategory hub page."""
        subcats = []
        seen = set()
        path_fragment = parent_url.split("/ecom")[-1]
        links = self.driver.find_elements(
            By.CSS_SELECTOR, f'a[href*="{path_fragment}/"]'
        )
        for link in links:
            try:
                url = link.get_attribute('href')
                if not url or url in seen or url == parent_url:
                    continue
                # Only direct children (one extra path segment)
                if not url.startswith(parent_url + '/'):
                    continue
                remainder = url[len(parent_url) + 1:]
                if '/' in remainder:
                    continue

                slug = remainder
                # Use visible text if available, otherwise derive from slug
                name = link.text.strip()
                if not name:
                    name = slug.replace('_', ' ').replace('-', ' ').title()

                subcats.append({'name': name, 'url': url, 'slug': slug})
                seen.add(url)
            except NoSuchElementException:
                continue
        return subcats

    def _wait_for_products(self):
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'article[data-testid="product-pod"]')
                )
            )
        except TimeoutException:
            print("  ✗ Timeout waiting for products")

    def _extract_stubs(self, category_slug: str) -> list:
        """Extract product stubs from the currently loaded page."""
        stubs = []
        pods = self.driver.find_elements(
            By.CSS_SELECTOR, 'article[data-testid="product-pod"]'
        )
        for pod in pods:
            try:
                pid = pod.get_attribute('data-product-id')
                if pid in self.seen_product_ids:
                    continue
                link = pod.find_element(
                    By.CSS_SELECTOR, 'a[href*="/products/"]'
                )
                href = link.get_attribute('href')
                url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                self.seen_product_ids.add(pid)
                stubs.append({
                    'product_id': pid,
                    'url': url,
                    'category': category_slug,
                })
            except NoSuchElementException:
                continue
        print(f"  Found {len(stubs)} products on page")
        return stubs

    def _paginate_and_collect(self, category_slug: str) -> list:
        """Click 'Load more' repeatedly and collect new product stubs."""
        all_new = []
        self.driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
        time.sleep(2)

        for attempt in range(100):
            btn = self._find_load_more()
            if not btn:
                print(f"  ✓ No more items (clicked {attempt} times)")
                break

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", btn
            )
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(4)

            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            new_stubs = self._extract_stubs(category_slug)
            all_new.extend(new_stubs)

            if not new_stubs:
                print("  ✓ No new products loaded")
                break

            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(2)

        return all_new

    def _find_load_more(self):
        css = [
            'button[data-testid="load-more"]',
            'button[class*="load-more"]',
            'button[class*="show-more"]',
        ]
        xpaths = [
            '//button[contains(translate(.,"LOAD","load"),"load more")]',
            '//button[contains(translate(.,"SHOW","show"),"show more")]',
        ]
        for sel in css:
            try:
                b = self.driver.find_element(By.CSS_SELECTOR, sel)
                if b.is_displayed() and b.is_enabled():
                    return b
            except NoSuchElementException:
                continue
        for xp in xpaths:
            try:
                b = self.driver.find_element(By.XPATH, xp)
                if b.is_displayed() and b.is_enabled():
                    return b
            except NoSuchElementException:
                continue
        return None

    # ------------------------------------------------------------------
    # Phase 2: enrich each product from its detail page __NEXT_DATA__
    # ------------------------------------------------------------------

    def enrich_product(self, stub: Dict) -> Optional[Dict]:
        """Visit a product page and extract key fields from __NEXT_DATA__.
        We only keep fields needed for the product catalogue and for
        matching against Open Food Facts (barcode, name, brand). Detailed
        nutrition/ingredients will come from Open Food Facts in Part B."""
        try:
            self.driver.get(stub['url'])
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))
            time.sleep(3)

            # Locate the __NEXT_DATA__ script tag
            try:
                script = self.driver.find_element(By.ID, '__NEXT_DATA__')
            except NoSuchElementException:
                script = None
                for s in self.driver.find_elements(By.TAG_NAME, 'script'):
                    sid = s.get_attribute('id') or ''
                    if 'next' in sid.lower() or 'data' in sid.lower():
                        script = s
                        break

            if not script:
                return None

            raw = script.get_attribute('innerHTML')
            if not raw or len(raw) < 100:
                return None

            pj = (
                json.loads(raw)
                .get('props', {})
                .get('pageProps', {})
                .get('product', {})
            )
            if not pj:
                return None

            barcodes = pj.get('barCodes', [])
            images = pj.get('images', {})

            return {
                'product_id': pj.get('lineNumber'),
                'name': pj.get('name'),
                'brand': pj.get('brand'),
                'price': pj.get('displayPrice'),
                'size': pj.get('size'),
                'url': stub['url'],
                'category': stub['category'],
                'barcode': barcodes[0] if barcodes else None,
                'image_url': images.get('large') or images.get('medium'),
                'product_type': pj.get('productType'),
                'scraped_at': datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"Error: {str(e)[:40]}", end=" ")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def handle_cookies(self):
        try:
            btn = self.driver.find_element(
                By.CSS_SELECTOR, 'button[data-testid="accept-all"]'
            )
            if btn.is_displayed():
                btn.click()
                time.sleep(2)
        except NoSuchElementException:
            try:
                btn = self.driver.find_element(
                    By.XPATH, '//button[contains(text(), "Accept")]'
                )
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
            except NoSuchElementException:
                pass

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def print_summary(self):
        total = len(self.all_products)
        if total == 0:
            print("\nNo products collected.")
            return
        with_barcode = sum(1 for p in self.all_products if p.get('barcode'))

        print(f"\n{'='*60}")
        print(f"✓ Saved {total} products to: {self.output_path}")
        print(f"  With barcode: {with_barcode}/{total}")
        print(f"{'='*60}")


# ----------------------------------------------------------------------

def main():
    scraper = WaitroseScraper(headless=False, max_categories=2)
    products = scraper.scrape_all()
    print(f"\n✓ Done — {len(products)} products collected.")
    return products


if __name__ == "__main__":
    main()