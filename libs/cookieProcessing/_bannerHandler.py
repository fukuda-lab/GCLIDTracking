import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

def cookie_banner_handler(driver, mode="DENY_ALL", timeout=10):
    clicked_button_text = None
    """
    Auto click cookie banner (Accept/Reject) for multi-language, multi-CMP.
    
    mode: "accept" hoặc "reject"
    """

    # ============================
    # 1) Các text thường gặp trong nhiều ngôn ngữ
    # ============================
    accept_keywords = [
        "accept", "agree", "akkoord", "accepteren", "allow",
        "aceptar", "oui", "d'accord", "sì", "承諾", "同意", "수락",
        "cho phép", "đồng ý", "approve", "consent"
    ]

    reject_keywords = [
        "reject", "deny", "refuse", "weigeren",
        "rechazar", "non", "rifiuta", "拒否", "否", "거부",
        "từ chối", "không đồng ý", "decline", "do not consent"
    ]

    # chọn list theo mode
    target_keywords = accept_keywords if mode == "ALLOW_ALL" else reject_keywords

    # ============================
    # 2) danh sách selectors phổ biến (CMP banners)
    # ============================
    common_selectors = [
        # OneTrust
        "button#onetrust-accept-btn-handler",
        "button#onetrust-reject-all-handler",

        # Cookiebot
        "button#CybotCookiebotDialogBodyLevelButtonAccept",
        "button#CybotCookiebotDialogBodyButtonDecline",

        # Google EU
        "button[aria-label='Reject all']",
        "button[aria-label='Accept all']",

        # Axeptio
        "button.ax-accept-all",
        "button.ax-deny-all",

        # Didomi
        "button.didomi-accept-all",
        "button.didomi-reject-all",

        ".save-preference-btn",
        ".btn-accept",
        ".btn-reject",
        ".cookie-accept",
        ".cookie-decline",
    ]

    # ============================
    # 3) thử click theo selector cố định
    # ============================
    for sel in common_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            clicked_button_text = btn.text
            print(clicked_button_text)
            btn.click()
            time.sleep(1)
            return True
        except:
            pass

    # ============================
    # 4) Tìm tất cả button → match theo text đa ngôn ngữ
    # ============================
    '''
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button") + \
                  driver.find_elements(By.XPATH, "//a")  # đôi khi banner dùng <a>
    except:
        buttons = []
    '''

    try:
        banner_containers = driver.find_elements(By.XPATH,"//*[contains(@id,'cookie') or contains(@class,'cookie') or contains(@id,'consent') or contains(@class,'consent') or contains(@id,'sp_') or contains(@class,'sp_')]")
        buttons = []
        for bc in banner_containers:
            try:
                buttons += bc.find_elements(By.TAG_NAME, "button")
                buttons += bc.find_elements(By.TAG_NAME, "a")
            except:
                pass
    except:
        buttons = []


    for btn in buttons:
        try:
            text = btn.text.strip().lower()
            if any(k in text for k in target_keywords):
                try:
                    clicked_button_text = btn.text
                    print(clicked_button_text)
                    btn.click()
                    time.sleep(1)
                    return True
                except:
                    pass
        except StaleElementReferenceException:
            continue

    # ============================
    # 5) thử tìm button theo XPath chứa text
    # ============================
    for k in target_keywords:
        xpath = f"//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{k}')]"
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                try:
                    clicked_button_text = el.text
                    print(clicked_button_text)
                    el.click()
                    time.sleep(1)
                    return True
                except:
                    pass
        except:
            continue

    # ============================
    # Không tìm thấy banner
    # ============================
    return False