from flask import Flask, render_template, request, send_file, jsonify
import requests
from bs4 import BeautifulSoup
import os
import tempfile
from urllib.parse import urlparse
import re

app = Flask(__name__)

def is_valid_url(url):
    """Validate if the provided string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def clean_text(text):
    """Clean and format the extracted text with preserved paragraphs"""
    # Remove control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # Normalize Windows/Mac line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse 3+ newlines into just 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip trailing spaces on each line
    text = '\n'.join(line.strip() for line in text.splitlines())

    return text.strip()

def scrape_website(url):
    """Scrape content from the given URL"""
    try:
        # Enhanced headers to better mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Create session for better handling
        session = requests.Session()
        session.headers.update(headers)
        
        # Make request with timeout and follow redirects
        response = session.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # Get the response text directly - requests handles encoding automatically
        html_content = response.text
        
        # Check if content is readable
        if len(html_content) < 100:
            return {
                'success': False,
                'error': 'Content too short. The page might be empty or blocked.'
            }
        
        # Check if content looks like HTML (contains common HTML tags)
        html_indicators = ['<html', '<head', '<body', '<div', '<p', '<h1', '<h2', '<h3', '<title']
        has_html_tags = any(tag in html_content.lower() for tag in html_indicators)
        
        if not has_html_tags:
            return {
                'success': False,
                'error': 'Content does not appear to be HTML. This website may be blocked or use special encoding.'
            }
        
        # Parse HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract text content
        text = soup.get_text()
        
        # Check if content is readable (not binary/encoded)
        if len(text) > 0:
            # Check if content looks like readable text
            readable_chars = sum(1 for c in text[:200] if c.isprintable() or c.isspace())
            total_chars = min(len(text[:200]), 200)
            
            if total_chars > 0 and readable_chars / total_chars < 0.3:
                return {
                    'success': False,
                    'error': 'Content appears to be encoded or compressed. This website may use special encoding or be blocked.'
                }
        
        # Check if we got meaningful content
        if len(text.strip()) < 10:
            return {
                'success': False,
                'error': 'No readable content found. The page might be empty or use JavaScript to load content.'
            }
        
        # Clean the text
        cleaned_text = clean_text(text)
        
        # Only check for completely empty content
        if len(cleaned_text.strip()) == 0:
            return {
                'success': False,
                'error': 'No readable content found. The page might be empty or use JavaScript to load content.'
            }
        
        return {
            'success': True,
            'content': cleaned_text,
            'title': soup.title.string if soup.title else 'Untitled',
            'url': url
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            return {
                'success': False,
                'error': 'Access denied (403 Forbidden). This website blocks automated requests. Try a different website or contact the site administrator.'
            }
        elif e.response.status_code == 404:
            return {
                'success': False,
                'error': 'Page not found (404). Please check the URL and try again.'
            }
        else:
            return {
                'success': False,
                'error': f'HTTP Error {e.response.status_code}: {str(e)}'
            }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f'Failed to fetch URL: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error processing content: {str(e)}'
        }

@app.route('/')
def index():
    """Main page with URL input form"""
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """Handle URL scraping request"""
    url = request.form.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'Please provide a URL'})
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    if not is_valid_url(url):
        return jsonify({'success': False, 'error': 'Please provide a valid URL'})
    
    # Scrape the website
    result = scrape_website(url)
    
    if not result['success']:
        return jsonify(result)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')
    
    # Write content to file
    temp_file.write(f"Scraped Content from: {result['url']}\n")
    temp_file.write(f"Title: {result['title']}\n")
    temp_file.write("=" * 50 + "\n\n")
    temp_file.write(result['content'])
    temp_file.close()
    
    return jsonify({
        'success': True,
        'filename': os.path.basename(temp_file.name),
        'title': result['title'],
        'url': result['url']
    })

@app.route('/download/<filename>')
def download_file(filename):
    """Download the scraped content as text file"""
    try:
        # Find the temporary file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=f'scraped_content_{filename}')
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8089)
