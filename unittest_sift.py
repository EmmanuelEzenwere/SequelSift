
"""
Test suite for Sequel Sift module.

Tests the main functionality including:
- Text cleaning
- Company name extraction
- Phrase analysis
- Web scraping with retry logic
- Full website analysis
"""

import unittest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
import nltk

from sift import (  
    SequelSift, 
    text_cleaner, 
    extract_company_name, 
    analyze_phrase
)

# Download required NLTK data
nltk.download('words')
nltk.download('maxent_ne_chunker_tab')
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')

class TestTextCleaner(unittest.TestCase):
    """Test cases for text_cleaner function"""
    
    def test_basic_cleaning(self):
        """Test basic text cleaning functionality"""
        test_cases = [
            ("Hello, world!", "Hello world"),
            ("Multiple! Sentences. Here.", "Multiple,Sentences,Here"),
            ("Special@#$%^&* chars", "Special chars"),
            ("Extra    spaces", "Extra spaces"),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = text_cleaner(input_text)
                # Normalize spaces in result
                result = ' '.join(result.split())
                self.assertEqual(result, expected)

class TestCompanyNameExtraction(unittest.TestCase):
    """Test cases for company name extraction"""
    
    def test_analyze_phrase(self):
        """Test phrase analysis for company names"""
        test_cases = [
            ("Twinn Health", ("Twinn Health", 2, 2)),
            ("Home", ("Home", 0, 1)),
            ("Digital Platform", ("Digital Platform", 2, 2)),
            ("Simple Text", (None, 0, 2))
        ]
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                self.assertEqual(analyze_phrase(input_text), expected)
    
    def test_extract_company_name(self):
        """Test company name extraction from title text"""
        test_cases = [
            ("Home | Twinn Health", "Twinn Health"),
            ("tonestro | Learn to play", "tonestro"),
            ("Digital Sales Room | trumpet", "trumpet"),
            ("Prewave | Supply Chain", "Prewave"),
            ("Simple Text | Another Text", "Simple Text")  # Default to shorter
        ]
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = extract_company_name(input_text)
                self.assertEqual(result, expected)

class TestSequelSift(unittest.TestCase):
    """Test cases for SequelSift class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.sift = SequelSift()
        self.sample_html = """
        <html>
            <head>
                <title>Home | Test Company</title>
                <meta property="og:site_name" content="Test Company">
                <meta name="description" content="Company description">
            </head>
            <body>
                <div class="feature-header">
                    <h3>Product Name</h3>
                </div>
                <p>John Smith, Founder of Test Company</p>
                <a href="/about">About Us</a>
                <div class="product-block-details">
                    <h3 class="product-block-title">Product Title</h3>
                </div>
                <div class="product-list-title">
                    <h2>Feature Title</h2>
                    <p>Feature Description</p>
                </div>
            </body>
        </html>
        """
        self.soup = BeautifulSoup(self.sample_html, 'html.parser')
    
    @patch('requests.get')
    def test_fetch_with_retry(self, mock_get):
        """Test webpage fetching with retry logic"""
        # Mock successful response
        mock_response = Mock()
        mock_response.text = self.sample_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.sift._fetch_with_retry('https://example.com')
        self.assertIsNotNone(result)
        
        # Test retry on failure
        mock_get.reset_mock()
        mock_get.side_effect = [Exception("Error"), Exception("Error"), mock_response]
        result = self.sift._fetch_with_retry('https://example.com')
        self.assertIsNotNone(result)
        self.assertEqual(mock_get.call_count, 3)
    
    def test_extract_company_name_from_html(self):
        """Test company name extraction from HTML"""
        result = self.sift._extract_company_name(self.soup)
        self.assertEqual(result, "Test Company")
    
    def test_extract_description(self):
        """Test description extraction"""
        result = self.sift._extract_description(self.soup)
        self.assertEqual(result, "Company description")
    
    def test_find_founders(self):
        """Test founder information extraction"""
        result = self.sift._find_founders(self.soup)
        self.assertIsNotNone(result)
        self.assertTrue(any("john smith" in name.lower() for name in result))
    
    def test_extract_product_info(self):
        """Test product information extraction"""
        result = self.sift._extract_product_info(self.soup)
        self.assertIn("Product Name", result['products'])
        self.assertIn("Product Title", result['products'])
        self.assertIn("Feature Title", result['features'])
        self.assertIn("Feature Description", result['descriptions'])
    
    def test_find_about_page(self):
        """Test about page URL extraction"""
        result = self.sift._find_about_page("https://example.com", self.soup)
        self.assertEqual(result, "https://example.com/about")
    
    def test_analyze_website(self):
        """Test full website analysis"""
        with patch.object(self.sift, '_fetch_with_retry') as mock_fetch:
            mock_fetch.return_value = self.soup
            result = self.sift.analyze_website("example.com")
            
            self.assertIsInstance(result, dict)
            self.assertEqual(result['company_name'], "Test Company")
            self.assertEqual(result['description'], "Company description")
            self.assertIsNotNone(result['founders'])
            self.assertIsNotNone(result['product_info'])
            
            # Test error handling
            mock_fetch.return_value = None
            result = self.sift.analyze_website("invalid.com")
            self.assertIsNone(result['company_name'])
    
    def test_analyze_website_with_about_page(self):
        """Test website analysis with about page extraction"""
        with patch.object(self.sift, '_fetch_with_retry') as mock_fetch:
            # Create about page soup with additional founder
            about_html = """
            <html><body>
                <p>Jane Doe, Co-Founder</p>
            </body></html>
            """
            about_soup = BeautifulSoup(about_html, 'html.parser')
            
            # Mock responses for main page and about page
            mock_fetch.side_effect = [self.soup, about_soup]
            
            result = self.sift.analyze_website("example.com")
            self.assertIsInstance(result['founders'], set)
            self.assertTrue(len(result['founders']) >= 2)  # Should find both founders

def main():
    unittest.main(verbosity=2)

if __name__ == '__main__':
    main()
