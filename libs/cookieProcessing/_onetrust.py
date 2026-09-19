import time
from selenium.webdriver.common.by import By

def handle_onetrust(driver, mode="DENY_ALL"):
    try:
        if mode == "ALLOW_ALL":
            sel = "button#onetrust-accept-btn-handler"
        else:
            sel = "button#onetrust-reject-all-handler"

        btn = driver.find_element(By.CSS_SELECTOR, sel)
        btn.click()
        time.sleep(1)
        return True
    except:
        return False
