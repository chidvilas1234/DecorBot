import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import os
from urllib.parse import urljoin
import re

class JenniferFurnitureScraper:
    def __init__(self, base_url="https://www.jenniferfurniture.com/"):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.all_products = []
        self.debug = True  # Set to True to print debug information
    
    def debug_print(self, message):
        """Print debug information if debug mode is enabled"""
        if self.debug:
            print(f"DEBUG: {message}")
    
    def get_page_html(self, url):
        """Fetch HTML content of the specified URL"""
        try:
            self.debug_print(f"Fetching URL: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching page {url}: {e}")
            return None
    
    def parse_product_page(self, product_url):
        """Extract details from a product page"""
        html = self.get_page_html(product_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        self.debug_print(f"Parsing product page: {product_url}")
        
        # Extract product details
        product = {}
        
        # Title
        title_selectors = [
            'h1.product-title',
            'h1.title',
            'h1.product-single__title',
            'h1[itemprop="name"]',
            '.product-title h1',
            '#product-title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                product['title'] = title_elem.text.strip()
                self.debug_print(f"Found title: {product['title']} using selector: {selector}")
                break
        
        if 'title' not in product:
            # Try to find any h1 that might contain the title
            h1_elems = soup.find_all('h1')
            if h1_elems:
                product['title'] = h1_elems[0].text.strip()
                self.debug_print(f"Found title using generic h1: {product['title']}")
            else:
                product['title'] = "N/A"
                self.debug_print("No title found")
        
        # Price
        price_selectors = [
            'span.price-new',
            '.price',
            '.product-price',
            'span[itemprop="price"]',
            '.product-single__price',
            '#product-price',
            'div.price-box span.regular-price'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.text.strip()
                # Clean up price text (remove non-price characters)
                price_text = re.sub(r'[^\d.,]', '', price_text)
                product['price'] = price_text
                self.debug_print(f"Found price: {product['price']} using selector: {selector}")
                break
        
        if 'price' not in product:
            # Try to find price using common patterns
            price_pattern = re.compile(r'(\$\d+(?:\.\d{2})?)')
            price_matches = price_pattern.findall(str(soup))
            if price_matches:
                product['price'] = price_matches[0]
                self.debug_print(f"Found price using regex: {product['price']}")
            else:
                product['price'] = "N/A"
                self.debug_print("No price found")
        
        # Original price if on sale
        original_price_selectors = [
            'span.price-old',
            '.compare-price',
            '.product-single__price--compare',
            '.was-price',
            'span.old-price'
        ]
        
        for selector in original_price_selectors:
            orig_price_elem = soup.select_one(selector)
            if orig_price_elem:
                orig_price_text = orig_price_elem.text.strip()
                # Clean up price text
                orig_price_text = re.sub(r'[^\d.,]', '', orig_price_text)
                product['original_price'] = orig_price_text
                self.debug_print(f"Found original price: {product['original_price']} using selector: {selector}")
                break
        
        if 'original_price' not in product:
            product['original_price'] = product.get('price', 'N/A')
        
        # SKU
        sku_selectors = [
            'div.sku',
            '.product-sku',
            'span[itemprop="sku"]',
            '.product-single__sku'
        ]
        
        for selector in sku_selectors:
            sku_elem = soup.select_one(selector)
            if sku_elem:
                sku_text = sku_elem.text.strip()
                # Clean up SKU text (remove "SKU:" prefix)
                sku_text = re.sub(r'^SKU:?\s*', '', sku_text, flags=re.IGNORECASE)
                product['sku'] = sku_text
                self.debug_print(f"Found SKU: {product['sku']} using selector: {selector}")
                break
        
        if 'sku' not in product:
            # Try to find SKU in the page source
            sku_pattern = re.compile(r'SKU:?\s*([A-Za-z0-9-]+)')
            sku_matches = sku_pattern.findall(str(soup))
            if sku_matches:
                product['sku'] = sku_matches[0]
                self.debug_print(f"Found SKU using regex: {product['sku']}")
            else:
                product['sku'] = "N/A"
                self.debug_print("No SKU found")
        
        # Description
        description_selectors = [
            'div.product-description',
            '.description',
            '#product-description',
            'div[itemprop="description"]',
            '.product-single__description',
            '.product-description-container'
        ]
        
        for selector in description_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                product['description'] = desc_elem.text.strip()
                self.debug_print(f"Found description using selector: {selector}")
                break
        
        if 'description' not in product:
            # Try to find description in meta tags
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                product['description'] = meta_desc.get('content')
                self.debug_print("Found description in meta tag")
            else:
                product['description'] = "N/A"
                self.debug_print("No description found")
        
        # Images
        image_selectors = [
            'div.product-image-main img',
            '.product-featured-image img',
            '.product-single__media img',
            'img[itemprop="image"]',
            '.product-single__photo img',
            'div.product-img-box img',
            '#product-featured-image'
        ]
        
        product['images'] = []
        
        for selector in image_selectors:
            image_elems = soup.select(selector)
            if image_elems:
                for img in image_elems:
                    img_url = img.get('src') or img.get('data-src')
                    if img_url:
                        full_img_url = urljoin(self.base_url, img_url)
                        product['images'].append(full_img_url)
                self.debug_print(f"Found {len(product['images'])} images using selector: {selector}")
                break
        
        if not product['images']:
            # Try to find any image in the product area
            all_images = soup.find_all('img')
            for img in all_images:
                img_url = img.get('src') or img.get('data-src')
                if img_url and ('product' in img_url.lower() or 'item' in img_url.lower()):
                    full_img_url = urljoin(self.base_url, img_url)
                    product['images'].append(full_img_url)
            self.debug_print(f"Found {len(product['images'])} images using generic image search")
        
        # Specifications/Details
        specs = {}
        spec_selectors = [
            'div.product-specification div.row',
            '.product-details table tr',
            '.product-specs table tr',
            'table.product-attributes tr',
            '.product-features li'
        ]
        
        for selector in spec_selectors:
            spec_elems = soup.select(selector)
            if spec_elems:
                for spec in spec_elems:
                    name_elem = spec.select_one('div.col-sm-4') or spec.select_one('th') or spec.select_one('td:first-child') or spec.select_one('strong')
                    value_elem = spec.select_one('div.col-sm-8') or spec.select_one('td:last-child') or spec.select_one('span')
                    
                    if name_elem and value_elem:
                        name = name_elem.text.strip()
                        value = value_elem.text.strip()
                        specs[name] = value
                
                self.debug_print(f"Found {len(specs)} specifications using selector: {selector}")
                break
        
        product['specifications'] = specs
        product['url'] = product_url
        
        return product
    
    def scrape_category_page(self, url):
        """Scrape products from a category page"""
        html = self.get_page_html(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        product_links = []
        
        # Try different selectors for product cards based on page structure
        product_selectors = [
            'div.product-layout div.product-thumb',
            '.product-grid .product-card',
            '.collection-grid .grid-product',
            '.products-grid .product-item',
            '.product-list .product',
            'ul.products li.product',
            '.grid-product__content',
            'article[data-product]',
            '.product-item',
            '.grid__item',
            '.product-card'
        ]
        
        product_cards = []
        used_selector = None
        
        for selector in product_selectors:
            product_cards = soup.select(selector)
            if product_cards:
                used_selector = selector
                self.debug_print(f"Found {len(product_cards)} product cards using selector: {selector}")
                break
        
        # If no product cards found with predefined selectors, try to find any links with product-related classes
        if not product_cards:
            product_cards = soup.select('a[href*="product"]') or soup.select('a[href*="/products/"]')
            if product_cards:
                self.debug_print(f"Found {len(product_cards)} product cards using href contains product")
        
        # Extract product links
        for card in product_cards:
            # Try to find direct link in card
            if card.name == 'a' and card.get('href'):
                link_elem = card
            else:
                # Try various selectors for links
                link_selectors = [
                    'div.caption h4 a',
                    'a.product-title',
                    'h2.product-title a',
                    'a.grid-product__link',
                    '.product-name a',
                    'a.product-link',
                    'h2 a',
                    'a.product-item-link',
                    '.product-card__title a',
                    'a[href*="product"]',
                    'a'  # As a last resort, try any link
                ]
                
                link_elem = None
                for selector in link_selectors:
                    link_elem = card.select_one(selector)
                    if link_elem and link_elem.get('href'):
                        break
            
            if link_elem and link_elem.get('href'):
                full_url = urljoin(self.base_url, link_elem.get('href'))
                if full_url not in product_links:  # Avoid duplicates
                    product_links.append(full_url)
        
        self.debug_print(f"Found {len(product_links)} product links on page {url}")
        
        # If no product links found yet, try to find all links that might be products
        if not product_links:
            all_links = soup.find_all('a')
            for link in all_links:
                href = link.get('href')
                if href and ('product' in href or '/p/' in href):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in product_links:
                        product_links.append(full_url)
            
            self.debug_print(f"Found {len(product_links)} product links using generic product link search")
        
        print(f"Found {len(product_links)} products on page {url}")
        
        products = []
        for link in product_links:
            product = self.parse_product_page(link)
            if product:
                products.append(product)
                # Be nice to the server with a small delay
                time.sleep(1)
        
        return products
    
    def get_next_page_url(self, url, html):
        """Extract the next page URL if available"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try different selectors for pagination
        next_link_selectors = [
            'ul.pagination li.active + li a',
            '.pagination .next a',
            'a.pagination__next',
            'a[rel="next"]',
            '.next-page a',
            '.pagination-next a',
            'a.next',
            'a.next-page',
            '.pagination .next',
            '.pagination a:contains("Next")',
            'a:contains("Next")'
        ]
        
        for selector in next_link_selectors:
            if selector.endswith(':contains("Next")'):
                # Handle special case for contains selector
                selector_name = selector.split(':')[0]
                elements = soup.select(selector_name)
                next_link = None
                for el in elements:
                    if el.text.strip().lower() == 'next':
                        next_link = el
                        break
            else:
                next_link = soup.select_one(selector)
            
            if next_link and next_link.get('href'):
                next_url = urljoin(self.base_url, next_link.get('href'))
                self.debug_print(f"Found next page URL: {next_url} using selector: {selector}")
                return next_url
        
        # Try to find pagination using regex patterns
        pagination_pattern = re.compile(r'page=(\d+)')
        current_page_match = pagination_pattern.search(url)
        if current_page_match:
            current_page = int(current_page_match.group(1))
            next_page = current_page + 1
            next_url = re.sub(r'page=\d+', f'page={next_page}', url)
            self.debug_print(f"Generated next page URL using regex: {next_url}")
            return next_url
        
        return None
    
    def scrape_multiple_pages(self, start_url, max_pages=4):
        """Scrape up to max_pages from the starting URL"""
        current_url = start_url
        page_count = 0
        
        while current_url and page_count < max_pages:
            print(f"Scraping page {page_count + 1}: {current_url}")
            html = self.get_page_html(current_url)
            if not html:
                break
            
            # Scrape products from current page
            products = self.scrape_category_page(current_url)
            self.all_products.extend(products)
            
            # Find next page URL
            next_url = self.get_next_page_url(current_url, html)
            
            # Check if we're going to a different page
            if next_url == current_url:
                self.debug_print("Next URL is the same as current URL, stopping pagination")
                break
                
            current_url = next_url
            page_count += 1
            
            # Be nice to the server with a delay between pages
            time.sleep(2)
        
        return self.all_products
    
    def save_to_json(self, filename="jennifer_products.json"):
        """Save scraped products to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.all_products, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(self.all_products)} products to {filename}")
    
    def save_to_csv(self, filename="jennifer_products.csv"):
        """Save scraped products to CSV file"""
        if not self.all_products:
            print("No products to save")
            return
        
        # Get all possible fields from all products
        fieldnames = ['title', 'price', 'original_price', 'sku', 'description', 'url']
        
        # Add specification fields
        spec_fields = set()
        for product in self.all_products:
            for spec in product.get('specifications', {}).keys():
                spec_fields.add(f"spec_{spec}")
        
        fieldnames.extend(sorted(spec_fields))
        fieldnames.append('images')
        
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in self.all_products:
                row = {
                    'title': product.get('title', ''),
                    'price': product.get('price', ''),
                    'original_price': product.get('original_price', ''),
                    'sku': product.get('sku', ''),
                    'description': product.get('description', ''),
                    'url': product.get('url', ''),
                    'images': '; '.join(product.get('images', []))
                }
                
                # Add specifications
                for spec_name, spec_value in product.get('specifications', {}).items():
                    row[f"spec_{spec_name}"] = spec_value
                
                writer.writerow(row)
        
        print(f"Saved {len(self.all_products)} products to {filename}")

# Example usage
if __name__ == "__main__":
    scraper = JenniferFurnitureScraper()
    
    # Use the collection URL you're trying to scrape
    start_url = "https://www.jenniferfurniture.com/collections/modern-heritage-mattresses.html"
    
    # Scrape up to 4 pages
    products = scraper.scrape_multiple_pages(start_url, max_pages=4)
    
    # Save results
    scraper.save_to_json()
    scraper.save_to_csv()