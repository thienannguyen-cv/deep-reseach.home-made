import os
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# --- Flask Configuration ---
app = Flask(__name__)
CORS(app) # Enable Cross-Origin Resource Sharing for frontend to call API

# --- Selenium WebDriver Configuration ---
def get_chrome_driver():
    """Initializes and returns a Chrome WebDriver using integrated Selenium Manager."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run browser in headless mode
    chrome_options.add_argument("--disable-gpu") # Disable GPU (necessary for headless)
    chrome_options.add_argument("--no-sandbox") # Disable sandbox (necessary for Linux/Docker environments)
    chrome_options.add_argument("--disable-dev-shm-usage") # Reduce /dev/shm usage (necessary for Docker)
    chrome_options.add_argument("--disable-extensions") # Disable extensions
    chrome_options.add_argument("--disable-infobars") # Disable infobars
    chrome_options.add_argument("--remote-debugging-port=9222") # Remote debugging port
    chrome_options.add_argument("--window-size=1920,1080") # Set window size
    
    # Use Selenium Manager to automatically download and manage chromedriver
    service = Service() 
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_page_full_text(url):
    """
    Crawls the given URL using Selenium and extracts the full visible text content.
    Handles dynamic content loaded by JavaScript.
    """
    driver = None
    try:
        driver = get_chrome_driver()
        driver.get(url)
        # Wait for the body element to be present, indicating the page has loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Get the page source after dynamic content has loaded
        page_source = driver.page_source
        
        # Use BeautifulSoup to parse the HTML and extract text
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Remove script and style elements as they are not part of the visible text content
        for script in soup(["script", "style"]):
            script.extract()
        
        text = soup.get_text()
        
        # Clean up text:
        # Break into lines and remove leading/trailing space on each line
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a single line each (e.g., "Headline1\nHeadline2" becomes "Headline1 Headline2")
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit text length to avoid exceeding LLM context window limits
        MAX_TEXT_LENGTH = 15000 # Increased limit for more comprehensive crawling
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "..." # Truncate and add ellipsis to indicate truncation
        
        return text
    except Exception as e:
        print(f"Error during crawl of {url}: {e}")
        return f"Cannot crawl content: {e}"
    finally:
        # Ensure the browser is closed even if an error occurs
        if driver:
            driver.quit()

# --- Define API Endpoints ---

@app.route('/api/crawl_url', methods=['POST'])
def handle_crawl_url():
    """
    API endpoint for the frontend to request a URL crawl and return text content.
    Input: {"url": "https://example.com"}
    Output: {"content": "Text content of the page..."} or {"error": "..."}
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing URL to crawl"}), 400

    url = data['url']
    print(f"Crawl request for URL: {url}")
    
    crawled_content = get_page_full_text(url)
    
    if "Cannot crawl content" not in crawled_content: # Simple check for error string
        return jsonify({"content": crawled_content})
    else:
        return jsonify({"error": crawled_content}), 500

# --- Serve Static Files (Frontend) ---
@app.route('/')
def serve_index():
    """Serves index.html as the main page."""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serves other static files if needed (e.g., separate CSS, JS)."""
    return send_from_directory('.', path)


if __name__ == '__main__':
    # Run the Flask app
    # Use a specific host and port to be accessible from other containers/frontend
    app.run(host='0.0.0.0', port=5000, debug=True)
