import allure
import time
from hamcrest import assert_that, equal_to
from helpers.allure_client import allure_attach

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys




def clear_text(element):
    length = len(element.get_attribute('value'))
    element.send_keys(length * Keys.BACKSPACE)


class TestLogin:
    pytesmark = [
        allure.epic('Мерч'),
        allure.label('version', 'V1'),
        allure.feature(f'Тест на регистрацию'),
        allure.label('layer', 'api'),
        allure.label('owner', 'sergfedorov'),
        allure.label('env', 'prod'),
        allure.description(
            f'Тесты на регистрацию'
        )
    ]

    def test_login(self):
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(url)
        time.sleep(5)
        connect = driver.find_element(By.XPATH, '//*[@id="root"]/div/div/header/div[1]/div/div/div[2]/button[1]')
        connect.click()
        time.sleep(5)
        registration = driver.find_element(By.XPATH, '//*[@id="root"]/div/div/div/div/div/form/div[3]/div/a/span')
        registration.click()
        login = driver.find_element(By.XPATH, '//*[@id="root"]/div/div/div/div/div/form/div[1]/div[1]/input')
        login.click()
        clear_text(login)
        login.send_keys('erty123ui@yandex.ru')
        password = driver.find_element(By.XPATH,
                                       '/html/body/div[1]/div/div/div/div/div/form/div[1]/div[2]/div/div/input')
        password.click()
        clear_text(password)
        password.send_keys('Qwerty123')
        password_2 = driver.find_element(By.XPATH,
                                         '/html/body/div[1]/div/div/div/div/div/form/div[1]/div[3]/div/div/input')
        password_2.click()
        clear_text(password_2)
        password_2.send_keys('Qwerty123')
        final = driver.find_element(By.XPATH, '//*[@id="root"]/div/div/div/div/div/form/div[2]/button')
        final.click()
        time.sleep(5)
        check = driver.find_element(By.XPATH, '//*[@id="root"]/div/div/div/div/div/h4')
        a = check.text
        assert_that(a, equal_to('Истории обменов нет'), 'Не найдено')
        driver.quit()
