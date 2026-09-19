import time
from selenium.webdriver.common.by import By

def handle_didomi(driver, mode="DENY_ALL"):
    selectors = {
        "ALLOW_ALL": "button.didomi-accept-all",
        "DENY_ALL":  "button.didomi-reject-all"
    }
    try:
        btn = driver.find_element(By.CSS_SELECTOR, selectors[mode])
        btn.click()
        time.sleep(1)
        return True
    except:
        return False
