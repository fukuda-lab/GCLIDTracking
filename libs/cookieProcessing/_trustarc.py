import time
from selenium.webdriver.common.by import By

def handle_trustarc(driver, mode="DENY_ALL"):
    try:
        iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='trustarc']")
        driver.switch_to.frame(iframe)

        if mode == "ALLOW_ALL":
            txt = "Accept"
        else:
            txt = "Reject"

        xpath = f"//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{txt.lower()}')]"

        btn = driver.find_element(By.XPATH, xpath)
        btn.click()
        time.sleep(1)
        driver.switch_to.default_content()
        return True

    except:
        driver.switch_to.default_content()
        return False
