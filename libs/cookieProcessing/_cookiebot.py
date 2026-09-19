import time
from selenium.webdriver.common.by import By

def handle_cookiebot(driver, mode="DENY_ALL"):
    try:
        if mode == "ALLOW_ALL":
            sel = "button#CybotCookiebotDialogBodyLevelButtonAccept"
        else:
            sel = "button#CybotCookiebotDialogBodyButtonDecline"

        btn = driver.find_element(By.CSS_SELECTOR, sel)
        btn.click()
        time.sleep(1)
        return True
    except:
        return False
