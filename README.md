# Web Content Scraper

A simple and fast web application that scrapes content from any website and allows users to download it as a text file.

## Features

- 🌐 **Simple URL Input**: Just enter any website URL
- 🚀 **Fast Scraping**: Quick content extraction with proper error handling
- 📄 **Clean Text Output**: Removes HTML tags and formats content nicely
- 💾 **Easy Download**: Download scraped content as a text file
- 📱 **Responsive Design**: Works on desktop and mobile devices
- ⚡ **Lightweight**: Minimal dependencies and fast performance

## Installation

1. **Clone or download this project**
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Run the application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and go to: `http://localhost:8077`

3. **Enter a URL** of any website you want to scrape

4. **Click "Scrape Content"** and wait for the content to be extracted

5. **Download the text file** with the scraped content

## How it Works

- The app uses **Flask** for the web framework
- **BeautifulSoup** for HTML parsing and content extraction
- **Requests** for fetching web pages
- Content is cleaned and formatted for easy reading
- Files are temporarily stored and served for download

## Supported Websites

Works with most websites including:
- News articles
- Blog posts
- Documentation pages
- Wikipedia articles
- And many more!

## Requirements

- Python 3.6+
- Flask
- BeautifulSoup4
- Requests
- LXML

## Error Handling

The app includes robust error handling for:
- Invalid URLs
- Network timeouts
- Blocked requests
- Malformed HTML
- Server errors

## Security Features

- URL validation
- Request timeouts
- Proper error messages
- Temporary file cleanup

Enjoy scraping! 🎉
