import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import json
from concurrent.futures import ThreadPoolExecutor

class CompanyAnalyzer:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def analyze_website(self, domain):
        try:
            # Ensure domain has proper format
            if not domain.startswith(('http://', 'https://')):
                domain = 'https://' + domain
            
            # Fetch main page
            response = requests.get(domain, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Initialize results dictionary
            result = {
                'domain': domain,
                'company_name': self._extract_company_name(soup),
                'description': self._extract_description(soup),
                'founders': self._find_founders(soup),
                'product_info': self._extract_product_info(soup)
            }
            
            # Try to find additional pages
            about_page = self._find_about_page(domain, soup)
            if about_page:
                about_soup = BeautifulSoup(requests.get(about_page, headers=self.headers).text, 'html.parser')
                result['founders'].update(self._find_founders(about_soup))
            
            return result
            
        except Exception as e:
            return {
                'domain': domain,
                'error': str(e)
            }
    
    def _extract_company_name(self, soup):
        # Try different methods to find company name
        potential_names = []
        
        # Check meta tags
        meta_title = soup.find('meta', property='og:site_name')
        if meta_title:
            potential_names.append(meta_title['content'])
            
        # Check main title
        title = soup.find('title')
        if title:
            potential_names.append(title.text.split('|')[0].strip())
            
        return potential_names[0] if potential_names else None
    
    def _extract_description(self, soup):
        # Try to find meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            return meta_desc.get('content')
            
        # Try to find first meaningful paragraph
        first_p = soup.find('p')
        if first_p:
            return first_p.text.strip()
            
        return None
    
    def _find_founders(self, soup):
        founders = set()
        founder_keywords = ['founder', 'co-founder', 'ceo', 'chief executive']
        
        # Look for team sections or about sections
        for elem in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text = elem.text.lower()
            if any(keyword in text for keyword in founder_keywords):
                # Try to extract names (this is a simple approach)
                words = text.split()
                for i in range(len(words)-1):
                    if any(keyword in words[i] for keyword in founder_keywords):
                        potential_name = ' '.join(words[max(0, i-2):i]).strip()
                        if potential_name and len(potential_name.split()) >= 2:
                            founders.add(potential_name)
        
        return founders
    
    def _extract_product_info(self, soup):
        # Look for product-related information
        product_info = {
            'features': set(),
            'technologies': set()
        }
        
        # Look for common product-related keywords
        tech_keywords = ['ai', 'machine learning', 'blockchain', 'saas', 'platform']
        feature_sections = soup.find_all(['div', 'section'], class_=re.compile(r'feature|product|solution'))
        
        for section in feature_sections:
            text = section.text.lower()
            # Extract features
            if 'feature' in text:
                features = [line.strip() for line in text.split('\n') if line.strip()]
                product_info['features'].update(features[:3])  # Limit to top 3 features
                
            # Identify technologies
            for keyword in tech_keywords:
                if keyword in text:
                    product_info['technologies'].add(keyword)
        
        return {
            'features': list(product_info['features']),
            'technologies': list(product_info['technologies'])
        }
    
    def _find_about_page(self, base_url, soup):
        about_links = soup.find_all('a', href=re.compile(r'about|team', re.I))
        if about_links:
            return urljoin(base_url, about_links[0]['href'])
        return None

def main():
    domains = [
        'tonestro.com',
        'sendtrumpet.com',
        'prewave.com',
        'twinn.health',
        'kokoon.io'
    ]
    
    analyzer = CompanyAnalyzer()
    
    # Process domains in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(analyzer.analyze_website, domains))
    
    # Print results
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()