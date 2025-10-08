from flask import Flask, render_template, request, send_file, jsonify
import requests
from bs4 import BeautifulSoup
import os
import tempfile
from urllib.parse import urlparse
import re
from docx import Document
from docx.shared import Inches, RGBColor
from docx.oxml.shared import OxmlElement, qn

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

def add_hyperlink(paragraph, text, url):
    """Add a hyperlink to a paragraph - simplified approach"""
    # Add the link text with blue color and underline
    run = paragraph.add_run(text)
    run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
    run.font.underline = True
    
    # Add the URL in parentheses for reference
    paragraph.add_run(f" ({url})")
    return run

def create_word_document(title, url, html_content):
    """Create a Word document with proper HTML structure formatting"""
    doc = Document()
    
    print(f"DEBUG: HTML content length in create_word_document: {len(html_content)}")
    
    # Add title
    title_paragraph = doc.add_heading(title, 0)
    title_paragraph.alignment = 1  # Center alignment
    
    # Add URL
    url_paragraph = doc.add_paragraph()
    url_paragraph.add_run("Source URL: ").bold = True
    url_paragraph.add_run(url)
    url_paragraph.alignment = 1  # Center alignment
    
    # Add separator
    doc.add_paragraph("=" * 50)
    
    # Parse HTML content and add to document with proper formatting
    soup = BeautifulSoup(html_content, 'html.parser')
    print(f"DEBUG: Parsed HTML, looking for links...")
    
    # Add hyperlinks section FIRST - before removing navigation elements
    links = soup.find_all('a')
    print(f"DEBUG: Found {len(links)} total <a> tags in HTML")
    
    # Filter to only links with href attribute (including empty ones)
    links_with_href = [link for link in links if link.has_attr('href')]
    print(f"DEBUG: Found {len(links_with_href)} links with href attribute")
    
    # Debug: Show first few links
    print("DEBUG: First 5 links found:")
    for i, link in enumerate(links_with_href[:5]):
        text = link.get_text().strip()
        href = link.get('href', '')
        print(f"  {i+1}. '{text}' -> '{href}'")
    
    # Debug: Count different types of links
    internal_count = 0
    external_count = 0
    empty_count = 0
    
    for link in links_with_href:
        href = link.get('href', '')
        if not href:
            empty_count += 1
        elif href.startswith('#'):
            internal_count += 1
        elif href.startswith('http'):
            external_count += 1
    
    print(f"DEBUG: Link breakdown - Internal: {internal_count}, External: {external_count}, Empty: {empty_count}")
    
    if links_with_href:
        doc.add_paragraph("\n" + "=" * 50)
        doc.add_heading("📎 Hyperlinks Found", level=2)
        
        # Show ALL links found, including duplicates
        link_counter = 1
        
        for link in links_with_href:
            link_text = link.get_text().strip()
            link_url = link.get('href', '')
            print(f"DEBUG: Link {link_counter}: '{link_text}' -> '{link_url}'")
            
            if link_text:  # Show all links with text, even if href is empty
                paragraph = doc.add_paragraph()
                paragraph.add_run(f"{link_counter}. ").bold = True
                
                # Handle different types of links
                if not link_url:
                    # Empty href - just show the text
                    print(f"DEBUG: Processing empty href link: '{link_text}'")
                    paragraph.add_run(f"{link_text} (No link - text only)")
                elif link_url.startswith('#'):
                    # Internal anchor link
                    print(f"DEBUG: Processing internal link: {link_url}")
                    paragraph.add_run(f"{link_text} (Internal link: {link_url})")
                elif link_url.startswith('/'):
                    # Relative link
                    print(f"DEBUG: Processing relative link: {link_url}")
                    paragraph.add_run(f"{link_text} (Relative link: {link_url})")
                elif link_url.startswith('http://') or link_url.startswith('https://'):
                    # External link
                    print(f"DEBUG: Processing external link: {link_url}")
                    add_hyperlink(paragraph, link_text, link_url)
                else:
                    # Other types of links (mailto, tel, etc.)
                    print(f"DEBUG: Processing other link: {link_url}")
                    paragraph.add_run(f"{link_text} ({link_url})")
                
                link_counter += 1
    else:
        print("DEBUG: No links found in HTML")
    
    # NOW remove unwanted elements for content processing
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "menu"]):
        element.decompose()
    
    # Find the main content area (body or main content div)
    main_content = soup.find('body') or soup.find('main') or soup.find('article') or soup
    
    # Process content in document order
    _process_html_element(doc, main_content)
    
    # Add footer
    doc.add_paragraph("\n" + "=" * 50)
    footer_paragraph = doc.add_paragraph("Generated by Whitelabel IQ")
    footer_paragraph.alignment = 1  # Center alignment
    
    return doc

def _process_html_element(doc, element):
    """Recursively process HTML elements and add them to the Word document"""
    if not element:
        return
    
    # Skip NavigableString objects (text nodes)
    if not hasattr(element, 'name'):
        return
        
    # Handle different element types
    if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        # Add heading with appropriate level
        level = int(element.name[1])  # Extract number from h1, h2, etc.
        text = element.get_text().strip()
        if text:
            doc.add_heading(text, level)
            
    elif element.name == 'p':
        # Add paragraph with formatting
        text = element.get_text().strip()
        if text:
            paragraph = doc.add_paragraph()
            _add_formatted_text_to_paragraph(paragraph, element)
            
    elif element.name in ['ul', 'ol']:
        # Handle lists
        list_style = 'List Bullet' if element.name == 'ul' else 'List Number'
        for li in element.find_all('li', recursive=False):
            text = li.get_text().strip()
            if text:
                doc.add_paragraph(text, style=list_style)
                
    elif element.name == 'li':
        # Handle list items (fallback)
        text = element.get_text().strip()
        if text:
            doc.add_paragraph(text, style='List Bullet')
            
    elif element.name == 'br':
        # Line break
        doc.add_paragraph()
        
    elif element.name in ['div', 'section', 'article', 'span']:
        # Process children of container elements
        for child in element.children:
            if hasattr(child, 'name') and child.name:  # It's a tag
                _process_html_element(doc, child)
            elif hasattr(child, 'strip') and str(child).strip():  # It's text content
                doc.add_paragraph(str(child).strip())
                    
    elif element.name == 'a':
        # Handle hyperlinks
        link_text = element.get_text().strip()
        link_url = element.get('href', '')
        if link_text and link_url:
            paragraph = doc.add_paragraph()
            # Handle different types of links
            if link_url.startswith('#'):
                # Internal anchor link
                run = paragraph.add_run(link_text)
                run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
                run.font.underline = True
                paragraph.add_run(f" (Internal: {link_url})")
            elif link_url.startswith('/'):
                # Relative link
                run = paragraph.add_run(link_text)
                run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
                run.font.underline = True
                paragraph.add_run(f" (Relative: {link_url})")
            elif link_url.startswith('http://') or link_url.startswith('https://'):
                # External link
                add_hyperlink(paragraph, link_text, link_url)
            else:
                # Other types of links (mailto, tel, etc.)
                run = paragraph.add_run(link_text)
                run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
                run.font.underline = True
                paragraph.add_run(f" ({link_url})")
        elif link_text:
            doc.add_paragraph(link_text)
            
    elif element.name in ['strong', 'b', 'em', 'i']:
        # Handle inline formatting
        text = element.get_text().strip()
        if text:
            paragraph = doc.add_paragraph()
            run = paragraph.add_run(text)
            if element.name in ['strong', 'b']:
                run.bold = True
            elif element.name in ['em', 'i']:
                run.italic = True
                
    else:
        # For other elements, process their children
        for child in element.children:
            if hasattr(child, 'name') and child.name:  # It's a tag
                _process_html_element(doc, child)
            elif hasattr(child, 'strip') and str(child).strip():  # It's text content
                doc.add_paragraph(str(child).strip())

def _add_formatted_text_to_paragraph(paragraph, element):
    """Add text with formatting to a paragraph"""
    for content in element.contents:
        if hasattr(content, 'name') and content.name:
            if content.name == 'a':  # Handle hyperlinks
                link_text = content.get_text().strip()
                link_url = content.get('href', '')
                if link_text and link_url:
                    # Handle different types of links
                    if link_url.startswith('#'):
                        # Internal anchor link
                        run = paragraph.add_run(link_text)
                        run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
                        run.font.underline = True
                        paragraph.add_run(f" (Internal: {link_url})")
                    elif link_url.startswith('/'):
                        # Relative link
                        run = paragraph.add_run(link_text)
                        run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
                        run.font.underline = True
                        paragraph.add_run(f" (Relative: {link_url})")
                    elif link_url.startswith('http://') or link_url.startswith('https://'):
                        # External link
                        add_hyperlink(paragraph, link_text, link_url)
                    else:
                        # Other types of links (mailto, tel, etc.)
                        run = paragraph.add_run(link_text)
                        run.font.color.rgb = RGBColor(0, 102, 204)  # Blue color
                        run.font.underline = True
                        paragraph.add_run(f" ({link_url})")
                else:
                    paragraph.add_run(content.get_text())
            elif content.name in ['strong', 'b']:
                run = paragraph.add_run(content.get_text())
                run.bold = True
            elif content.name in ['em', 'i']:
                run = paragraph.add_run(content.get_text())
                run.italic = True
            else:
                paragraph.add_run(content.get_text())
        else:
            # It's a text node (NavigableString)
            text = str(content).strip()
            if text:
                paragraph.add_run(text)

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
            'html_content': html_content,
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
    
    print(f"DEBUG: Scrape result keys: {result.keys()}")
    print(f"DEBUG: HTML content length: {len(result.get('html_content', ''))}")
    
    # Create temporary text file
    temp_txt_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')
    temp_txt_file.write(f"Scraped Content from: {result['url']}\n")
    temp_txt_file.write(f"Title: {result['title']}\n")
    temp_txt_file.write("=" * 50 + "\n\n")
    temp_txt_file.write(result['content'])
    temp_txt_file.close()
    
    # Create temporary Word document
    temp_docx_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    temp_docx_file.close()
    
    # Create Word document with HTML content for proper formatting
    doc = create_word_document(result['title'], result['url'], result['html_content'])
    doc.save(temp_docx_file.name)
    
    return jsonify({
        'success': True,
        'txt_filename': os.path.basename(temp_txt_file.name),
        'docx_filename': os.path.basename(temp_docx_file.name),
        'title': result['title'],
        'url': result['url']
    })

@app.route('/download/<filename>')
def download_file(filename):
    """Download the scraped content as text or Word file"""
    try:
        # Find the temporary file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        if os.path.exists(file_path):
            # Determine file type and appropriate download name
            if filename.endswith('.txt'):
                download_name = f'scraped_content_{filename}'
                mimetype = 'text/plain'
            elif filename.endswith('.docx'):
                download_name = f'scraped_content_{filename}'
                mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            else:
                download_name = f'scraped_content_{filename}'
                mimetype = None
            
            return send_file(file_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8077)
