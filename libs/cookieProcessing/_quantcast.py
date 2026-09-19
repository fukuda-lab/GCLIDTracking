import time
from selenium.webdriver.common.by import By

def handle_quantcast(driver, mode="DENY_ALL"):
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='quantcast']")
        for iframe in iframes:
            driver.switch_to.frame(iframe)

            if mode == "ALLOW_ALL":
                sel = "button[mode='primary']"
            else:
                sel = "button[mode='secondary']"

            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for b in btns:
                if b.is_displayed():
                    b.click()
                    time.sleep(1)
                    driver.switch_to.default_content()
                    return True

            driver.switch_to.default_content()

    except:
        driver.switch_to.default_content()
        return False

    return False
