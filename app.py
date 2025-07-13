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

# --- Cấu hình Flask ---
app = Flask(__name__)
CORS(app) # Cho phép Cross-Origin Resource Sharing để frontend có thể gọi API

# --- Cấu hình Selenium WebDriver ---
def get_chrome_driver():
    """Khởi tạo và trả về một WebDriver Chrome sử dụng Selenium Manager tích hợp."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Chạy trình duyệt ẩn
    chrome_options.add_argument("--disable-gpu") # Vô hiệu hóa GPU (cần thiết cho headless)
    chrome_options.add_argument("--no-sandbox") # Vô hiệu hóa sandbox (cần thiết cho môi trường Linux/Docker)
    chrome_options.add_argument("--disable-dev-shm-usage") # Giảm việc sử dụng /dev/shm (cần thiết cho Docker)
    chrome_options.add_argument("--disable-extensions") # Vô hiệu hóa tiện ích mở rộng
    chrome_options.add_argument("--disable-infobars") # Vô hiệu hóa thanh thông tin
    chrome_options.add_argument("--remote-debugging-port=9222") # Cổng gỡ lỗi từ xa
    chrome_options.add_argument("--window-size=1920,1080") # Đặt kích thước cửa sổ để mô phỏng màn hình lớn
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36") # Giả mạo User-Agent

    # Selenium 4.6.0+ sẽ tự động quản lý driver khi Service() được gọi mà không có tham số
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_page_full_text(url: str) -> str:
    """
    Sử dụng Selenium để tải một URL, chờ trang tải hoàn tất,
    và trích xuất toàn bộ văn bản hiển thị từ phần thân trang.
    """
    driver = None
    try:
        driver = get_chrome_driver()
        driver.get(url)
        
        # Chờ cho đến khi document.readyState là 'complete'
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # Lấy toàn bộ mã nguồn HTML sau khi JavaScript đã thực thi
        page_source = driver.page_source
        
        # Phân tích cú pháp với BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Xóa các thẻ script và style để tránh lấy mã nguồn và CSS
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        
        # Lấy toàn bộ văn bản hiển thị từ phần thân trang
        body_text = soup.body.get_text(separator=' ', strip=True)
        
        # Giới hạn độ dài văn bản để tránh vượt quá giới hạn context của LLM
        # Có thể điều chỉnh con số này tùy thuộc vào model và nhu cầu
        max_text_length = 8000 # Giới hạn 8000 ký tự
        if len(body_text) > max_text_length:
            body_text = body_text[:max_text_length] + "..." # Cắt bớt và thêm dấu ba chấm
            
        return body_text
            
    except Exception as e:
        print(f"Lỗi khi crawl URL: {url}: {e}")
        return f"Không thể crawl nội dung từ {url}. Lỗi: {e}"
    finally:
        if driver:
            driver.quit() # Đảm bảo đóng trình duyệt sau khi sử dụng

# --- Định nghĩa các API Endpoint ---

@app.route('/api/crawl_url', methods=['POST'])
def handle_crawl_url():
    """
    Endpoint API để frontend yêu cầu crawl một URL và trả về nội dung văn bản.
    Input: {"url": "https://example.com"}
    Output: {"content": "Nội dung văn bản của trang..."} hoặc {"error": "..."}
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Thiếu URL để crawl"}), 400

    url = data['url']
    print(f"Yêu cầu crawl URL: {url}")
    
    crawled_content = get_page_full_text(url)
    
    if "Không thể crawl nội dung" not in crawled_content: # Kiểm tra chuỗi lỗi đơn giản
        return jsonify({"content": crawled_content})
    else:
        return jsonify({"error": crawled_content}), 500

# --- Phục vụ các file tĩnh (Frontend) ---
@app.route('/')
def serve_index():
    """Phục vụ file index.html làm trang chính."""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Phục vụ các file tĩnh khác nếu cần (ví dụ: CSS, JS riêng)."""
    return send_from_directory('.', path)


if __name__ == '__main__':
    # Chạy ứng dụng Flask.
    # host='0.0.0.0' để có thể truy cập từ mạng ngoài nếu cần.
    # port lấy từ biến môi trường PORT hoặc mặc định là 5000.
    # debug=True chỉ nên dùng trong môi trường phát triển.
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

