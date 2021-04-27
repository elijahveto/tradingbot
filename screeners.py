from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import os
from time import sleep


class Crawler:
    def __init__(self, url):
        path = os.environ.get('chromedriver_path')
        self.driver = webdriver.Chrome(executable_path=path)
        self.driver.get(url)

    def crawl(self, html):
        return BeautifulSoup(html, 'html.parser')

    def fb_login(self, driver):
        sleep(1)
        fb = driver.find_element_by_xpath('//span[.="Facebook"]')
        fb.click()
        sleep(2)
        base_window = driver.window_handles[0]
        fb_login_window = driver.window_handles[1]
        driver.switch_to.window(fb_login_window)
        sleep(1)
        consent = driver.find_element_by_css_selector('button[title="Alle akzeptieren"]')
        consent.click()
        sleep(1)
        email = driver.find_element_by_xpath('//*[@id="email"]')
        password = driver.find_element_by_xpath('//*[@id="pass"]')

        email.send_keys(os.environ.get('fb_mail'))
        password.send_keys(os.environ.get('fb_pw'))
        password.send_keys(Keys.ENTER)

        driver.switch_to.window(base_window)


class StockwitsScreener:
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



class TradingviewScreener:
    def __init__(self, filter):
        self.filter = filter
        self.url = 'https://www.tradingview.com/screener/'

    def run(self):
        crawler = Crawler(self.url)
        driver = crawler.driver
        login = driver.find_element_by_xpath('//a[.="Sign in"]')
        login.click()
        crawler.fb_login(driver)
        sleep(10)

        time_interval=driver.find_element_by_css_selector('div[data-name="screener-time-interval"]')
        time_interval.click()
        sleep(1)
        time_choice = driver.find_element_by_css_selector('div[data-interval="15m"]')
        time_choice.click()
        sleep(1)


        screener_choice = driver.find_element_by_css_selector('div[data-name="screener-filter-sets"]')
        screener_choice.click()
        sleep(1)
        sets = driver.find_element_by_class_name('tv-screener-popup__item--presets')
        screeners = sets.find_elements_by_class_name('tv-dropdown-behavior__item')

        for screener in screeners:
            if screener.text == self.filter:
                screener.click()
                sleep(2)

                html = driver.page_source
                content = crawler.crawl(html)
                tickers = [row.find(class_='tv-screener__symbol apply-common-tooltip').text for row in content.find_all(class_='tv-screener-table__result-row')]
                return tickers