from selenium import webdriver
from bs4 import BeautifulSoup
import os


class Crawler:
    def __init__(self, url):
        path = os.environ.get('chromedriver_path')
        self.driver = webdriver.Chrome(executable_path=path)
        self.driver.get(url)

    def crawl(self, html):
        return BeautifulSoup(html, 'html.parser')


class Screener:
    def __init__(self):
        self.urls = 'https://stocktwits.com/rankings/watchers'

    def run(self):
        data = []
        crawler = Crawler(self.urls)
        html = crawler.driver.page_source
        content = crawler.crawl(html)
        for row in content.find_all(class_='st_PaKabGw'):
            price = row.find(class_='st_vuSv7f4').text
            if price == '---':
                ticker = row.find(class_='st_3ua_jwB').text
                # exclude crypto
                if ticker[-2:] == '-X':
                    continue
                else:
                    data.append(ticker)
                    return data