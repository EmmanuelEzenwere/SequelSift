"""
Sequel Sift: A web scraping and analysis tool for startup company websites.

This module provides functionality to extract and analyze information from startup
company websites, including company names, descriptions, founder details, and 
product information. It uses BeautifulSoup for HTML parsing and NLTK for text
analysis.

Main Components:
    - SequelSift: Main class for website analysis
    - text_cleaner: Utility function for text normalization
    - extract_company_name: Function for company name extraction from text
    - analyze_phrase: Helper function for text analysis using NLTK

Dependencies:
    - requests: For making HTTP requests
    - beautifulsoup4: For HTML parsing
    - nltk: For natural language processing
    - pandas: For data organization
    - re: For regular expressions
    - urllib: For URL handling
    
Example Usage:
    >>> analyzer = SequelSift()
    >>> results = analyzer.analyze_website('example.com')
    >>> df = pd.DataFrame([results])

Author: Emmanuel Ezenwere
Version: 1.0.0
"""

import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd


import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk import pos_tag

nltk.download('words')
nltk.download('maxent_ne_chunker_tab')





def analyze_phrase(text):
    """
    Analyze a phrase for company name extraction
    Returns (phrase, number_of_proper_nouns, word count)
    """
    tokens = word_tokenize(text)
    tagged = pos_tag(tokens)
    
    proper_nouns = [word for word, tag in tagged if tag == 'NNP']
    is_single_word = len(tagged) == 1 and tagged[0][1].startswith('NN')
    
    if proper_nouns:
        return ' '.join(proper_nouns), len(proper_nouns), len(tokens)
    elif is_single_word:
        return tagged[0][0], 0, len(tokens)
    
    return None, 0, len(tokens)
    

def extract_company_name(text):
    """
    Extract company name from text using NLTK POS tagging
    
    Args:
        text (str): Input text containing company name
    Returns:
        str: Most likely company name
    """
    parts = [part.strip() for part in text.split('|')]
    if len(parts) != 2:
        return None
    
    left_phrase, left_proper_count, left_word_count = analyze_phrase(parts[0])
    right_phrase, right_proper_count, right_word_count = analyze_phrase(parts[1])
        
    #  If one side has all NNPs return it and if both have return the shorter one.
    if left_proper_count == left_word_count and right_proper_count == right_word_count:
        return left_phrase if left_word_count < right_word_count else right_phrase

    if left_proper_count == left_word_count:
        return left_phrase
    if right_proper_count == right_word_count:
        return right_phrase

    # If not all NNPs, return the shorter one
    return left_phrase if left_word_count < right_word_count else right_phrase


def text_cleaner(text):
    """Cleans and normalizes text by removing special characters and formatting.
    
    Processes text through the following steps:
    1. Splits text into sentences
    2. Removes all non-alphanumeric characters
    3. Strips whitespace
    4. Joins sentences with commas
    
    Args:
        text (str): Raw text string to be cleaned
        
    Returns:
        str: Cleaned text with sentences joined by commas
        
    Example:
        >>> text_cleaner("Hello, world! This is a test.")
        "Hello world,This is a test"
        
    Note:
        - Preserves only letters, numbers, and spaces
        - Removes punctuation, special characters, and extra whitespace
        - Maintains sentence boundaries using commas
    """
    # Tokenize text into sentences
    sentences = sent_tokenize(text)
    
    # Replace non-alphanumeric characters with spaces in each sentence
    processed_sentences = [re.sub(r'[^a-zA-Z0-9 ]+', ' ', sentence).strip() 
                         for sentence in sentences]
    
    # Join sentences with commas
    return ','.join(processed_sentences)


class SequelSift:
    """A class for analyzing company websites to extract key business information.
    
    This class provides methods to scrape and analyze company websites, extracting
    information such as company names, descriptions, founder details, and product
    information. It handles URL normalization, page fetching, and HTML parsing.
    
    Attributes:
        headers (dict): HTTP headers used for web requests, including user agent
        
    Methods:
        analyze_website: Main method to analyze a company's website
        _extract_company_name: Extracts company name from HTML
        _extract_description: Extracts company/product description
        _find_founders: Extracts founder information
        _extract_product_info: Extracts product-related information
        _find_about_page: Locates company's about/team page
        
    Example Usage:
        analyzer = SequelSift()
        result = analyzer.analyze_website('example.com')
        print(result['company_name'])
        print(result['description'])
    """
    
    def __init__(self):
        """Initialize with headers and retry settings"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
    def _fetch_with_retry(self, url):
        """Fetches a webpage with retry logic for reliability.
        
        Args:
            url (str): URL to fetch
            
        Returns:
            BeautifulSoup | None: Parsed HTML content or None if all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()  # Raise an HTTPError for bad responses
                return BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                 # Don't sleep on last attempt
                if attempt < self.max_retries - 1: 
                    print("re-attempting extraction")
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        return None
    
    def analyze_website(self, domain: str) -> dict:
        """Analyzes a website with retry logic for reliability."""
        result = {
            'domain': None,
            'company_name': None,
            'description': None,
            'founders': None,
            'product_info': None
        }
        
        try:
            # Ensure domain has proper format
            if not domain.startswith(('http://', 'https://')):
                if not domain.startswith('www.'):
                    domain = 'www.' + domain
                domain = 'https://' + domain
            
            result['domain'] = domain
            
            # Fetch main page with retry
            soup = self._fetch_with_retry(domain)
            if soup is None:
                print(f"Failed to fetch {domain} after {self.max_retries} attempts")
                return result
                
            # Extract information
            result['company_name'] = self._extract_company_name(soup)
            result['description'] = self._extract_description(soup)
            result['founders'] = self._find_founders(soup)
            result['product_info'] = self._extract_product_info(soup)
            
            # Try to find and fetch about page
            about_page = self._find_about_page(domain, soup)
            if about_page:
                about_soup = self._fetch_with_retry(about_page)
                if about_soup and result['founders'] is not None:
                    result['founders'].update(self._find_founders(about_soup))
                    
            return result
            
        except Exception as e:
            print(f'Error analyzing {domain}: {str(e)}')
            return result
        
        
    def _extract_company_name(self, soup):
        """Extracts company name from webpage HTML content.
        
        Attempts to find company name from multiple sources in HTML:
        1. Meta tags (og:site_name)
        2. Page title tag
        
        Args:
            soup (BeautifulSoup): Parsed HTML content in BeautifulSoup format
            
        Returns:
            str | None: First found company name from potential sources,
                    or None if no company name could be extracted
        """
        potential_names = []
        
        # Check meta tags
        meta_title = soup.find('meta', property='og:site_name')
        if meta_title:
            company_name = meta_title['content']
            potential_names.append(company_name)
            
        # Check main title
        title = soup.find('title')
        if title:
            company_name = extract_company_name(title.text)
            potential_names.append(company_name)
            
        return potential_names[0] if potential_names else None
    
    def _extract_description(self, soup):
        """Extracts website description from webpage HTML content.
        
        Searches for description in following priority order:
        1. Meta description tag
        2. First paragraph text
        
        The extracted text is cleaned before being returned.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content in BeautifulSoup format
            
        Returns:
            str | None: Cleaned description text if found,
                    None if no description could be extracted
        """
        # Try to find meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            return text_cleaner(meta_desc.get('content'))
            
        # Try to find first meaningful paragraph
        first_p = soup.find('p')
        if first_p:
            return text_cleaner(first_p.text.strip())
            
        return None
    
    def _find_founders(self, soup):
        """Extracts founder names from webpage HTML content.
        
        Searches through various HTML elements (p, div, headers) for founder-related 
        keywords and attempts to extract associated names. Looks for text patterns 
        where names typically appear before founder-related titles.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content in BeautifulSoup format
            
        Returns:
            set[str] | None: Set of cleaned founder names if found,
                            None if no founders could be identified or on error
                            
        Example extracted patterns:
            "John Smith, Founder"
            "Jane Doe, CEO"
            "Bob Wilson, Co-Founder & CTO"
        """
        try:
            founders = set()
            founder_keywords = ['founder', 'co-founder', 'ceo', 'chief executive']
            
            # Look for team sections or about sections
            for elem in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = elem.text.lower()
                if any(keyword in text for keyword in founder_keywords):
                    # Simple approach to extract names
                    words = text.split()
                    for i in range(len(words)-1):
                        if any(keyword in words[i] for keyword in founder_keywords):
                            # Look for name before the founder keyword
                            potential_name = ' '.join(words[max(0, i-2):i]).strip()
                            if potential_name and len(potential_name.split()) >= 2:
                                founders.add(text_cleaner(potential_name))
                                
            if founders == {}:
                return None
                
            return founders
            
        except Exception:
            return None
    
    def _extract_product_info(self, soup):
        """Extracts product-related information from webpage HTML content.
        
        Searches for product information in three main areas:
        1. Feature headers (class='feature-header')
        2. Product block details (class='product-block-details')
        3. Product list titles (class='product-list-title')
        
        Args:
            soup (BeautifulSoup): Parsed HTML content in BeautifulSoup format
            
        Returns:
            dict[str, list[str]]: Dictionary containing product information with keys:
                - products: List of product names/titles
                - features: List of product features/highlights
                - descriptions: List of product descriptions
                
        Note:
            Duplicates are removed while preserving the order of discovery.
            All text values are stripped of leading/trailing whitespace.
        """
        product_info = {
            'products': [],
            'features': [],
            'descriptions': []
        }
        
        # Extract from feature headers
        feature_headers = soup.find_all('div', class_='feature-header')
        for header in feature_headers:
            h3 = header.find('h3')
            if h3:
                product_info['products'].append(h3.text.strip())
                
        # Extract from product block details
        product_blocks = soup.find_all('div', class_='product-block-details')
        for block in product_blocks:
            title = block.find('h3', class_='product-block-title')
            if title:
                product_info['products'].append(title.text.strip())
                
        # Extract from product list titles
        list_titles = soup.find_all('div', class_='product-list-title')
        for title_block in list_titles:
            h2 = title_block.find('h2')
            p = title_block.find('p')
            if h2:
                product_info['features'].append(h2.text.strip())
            if p:
                product_info['descriptions'].append(p.text.strip())
                
        # Remove duplicates while preserving order
        for key in product_info:
            product_info[key] = list(dict.fromkeys(product_info[key]))
            
        return product_info
        
        
    def _find_about_page(self, base_url, soup):
        """Finds the URL of the company's about or team page.
        
        Searches for links containing 'about' or 'team' in their href attributes
        (case-insensitive) and constructs the full URL using the base URL.
        
        Args:
            base_url (str): The website's base URL (e.g., 'https://example.com')
            soup (BeautifulSoup): Parsed HTML content in BeautifulSoup format
            
        Returns:
            str | None: Full URL of the about/team page if found,
                    None if no relevant page could be found
                    
        Example:
            base_url: 'https://example.com'
            found href: '/about-us'
            returns: 'https://example.com/about-us'
        """
        about_links = soup.find_all('a', href=re.compile(r'about|team', re.I))
        if about_links:
            return urljoin(base_url, about_links[0]['href'])
        return None


startup_domains = [
        'tonestro.com',
        'sendtrumpet.com',
        'prewave.com',
        'twinn.health',
        'kokoon.io'
    ]


def main(domains):
    """ Run scraping on a list of websites.
    Args:
        domains (list): list of strings of company domains.
    """
    print("\n")
    print("-"*50)
    print("Sequel Sift -- Extracting Startup data...")
    print("-"*50)
    print("\n")

    analyzer = SequelSift()
    
    results = [analyzer.analyze_website(domain) for domain in domains]
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    company_infos = main(startup_domains)
    print(company_infos)
