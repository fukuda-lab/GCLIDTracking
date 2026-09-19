import time
from selenium.webdriver.common.by import By

def handle_sourcepoint(driver, mode="DENY_ALL"):
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[id^='sp_message_iframe_']")
        if not iframes:
            return False

        target_keywords = (
            ["accept", "agree", "ok", "got it", "yes"]
            if mode == "ALLOW_ALL"
            else ["reject", "decline", "no", "disagree"]
        )

        for iframe in iframes:
            driver.switch_to.frame(iframe)
            buttons = driver.find_elements(By.TAG_NAME, "button")

            for btn in buttons:
                txt = btn.text.strip().lower()
                if any(k in txt for k in target_keywords):
                    print(btn.text)
                    btn.click()
                    time.sleep(1)
                    driver.switch_to.default_content()
                    return True

            driver.switch_to.default_content()

    except:
        driver.switch_to.default_content()
        return False

    return False
