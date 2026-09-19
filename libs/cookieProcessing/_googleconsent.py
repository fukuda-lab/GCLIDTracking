import time
from selenium.webdriver.common.by import By

def handle_google_consent(driver, mode="DENY_ALL"):
    try:
        if mode == "ALLOW_ALL":
            sel = "button[aria-label='Accept all']"
        else:
            sel = "button[aria-label='Reject all']"

        btn = driver.find_element(By.CSS_SELECTOR, sel)
        btn.click()
        time.sleep(1)
        return True
    except:
        return False
