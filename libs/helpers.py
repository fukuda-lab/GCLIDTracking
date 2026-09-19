import base64
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def smart_delay(start_time, min_interval=60, fallback_sleep=2):
    elapsed = time.monotonic() - start_time
    if elapsed < min_interval:
        sleep_time = min_interval - elapsed
    else:
        sleep_time = fallback_sleep

    print(f"[INFO] Elapsed={elapsed:.2f}s → sleep {sleep_time:.2f}s")
    time.sleep(sleep_time)


def load_config(config_path="configs/config.json"):
    import json
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg

def save_config(profiles_zip, names, headless, outdir, 
                max_Pages, timeoutLoad, timeoutVisit, save_config=False, config_path="configs/config.json"):
    
    import json
    import os
    
    config = {
        "profiles_zip": profiles_zip,
        "names": names,
        "headless": headless,
        "outdir": outdir,
        "max_Pages": max_Pages,
        "timeoutLoad": timeoutLoad,
        "timeoutVisit": timeoutVisit,
    }
    if save_config:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        print(f"[OK] Config saved to {config_path}")
    
    return config


def loadSites(filepath):
    sites = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url:  # bỏ qua dòng rỗng
                sites.append(url)
    return sites


def is_infinite_scroll_page(driver, checks=3, wait=2, safari=False):
    """
    Kiểm tra trang có phải infinite scroll hay không bằng cách:
    - Cuộn xuống cuối
    - Chờ load nội dung
    - Nếu scrollHeight tăng nhiều lần → infinite scroll
    """
    heights = []
    if safari:
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.body != null")
        )

    for i in range(checks):
        # Lấy chiều cao hiện tại
        if safari:
            h1 = get_scroll_height(driver)
        else:
            h1 = driver.execute_script("return document.body.scrollHeight")
        heights.append(h1)

        # Scroll xuống đáy
        if safari:
            driver.execute_script("""
                                  const h = document.body ? document.body.scrollHeight : document.documentElement ? document.documentElement.scrollHeight : 0;
                                  window.scrollTo(0, h);
                                  """)
        else:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)

        # Lấy chiều cao sau khi chờ
        if safari:
            h2 = get_scroll_height(driver)
        else:
            h2 = driver.execute_script("return document.body.scrollHeight")
        heights.append(h2)

        # Nếu chiều cao tăng → có tải thêm nội dung
        if h2 > h1 + 200:  # tolerance threshold
            return True  # chắc chắn là infinite scroll

    # Không thấy tăng đáng kể → không phải infinite scroll
    return False

def scroll_infinite(driver, step=600, pause=1, max_idle=3, scroll_to_top=True, lite_mode=False):
    import time

    idle_count = 0


    last_height = driver.execute_script("return document.body.scrollHeight")

    while idle_count < max_idle:
        driver.execute_script("window.scrollBy(0, arguments[0]);", step)
        time.sleep(pause)

        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height <= last_height:
            idle_count += 1
        else:
            idle_count = 0
            last_height = new_height

    print("[INFO] Infinite scroll content exhausted.")

    if lite_mode == False:
        # ------------- SCROLL TO TOP -------------
        if scroll_to_top:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.8)
            print("[INFO] Returned to top of page.")

def get_scroll_height(driver):
    return driver.execute_script("""
        return document.body ? document.body.scrollHeight :
               document.documentElement ? document.documentElement.scrollHeight : 0;
    """)

# --- Scroll slowly to trigger lazy-load ads ---
def slow_scroll_page(driver, step=600, pause=0.5, lite_mode=False):
    import time
    """
    Slowly scroll down and back up to trigger lazy-loaded ads.
    """
    try:
        print("[INFO] Scrolling down to trigger lazy-load ads...")
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        current_scroll = 0

        # Scroll down
        while current_scroll < last_height:
            driver.execute_script(f"window.scrollTo(0, {current_scroll});")
            time.sleep(pause)
            current_scroll += step
            last_height = driver.execute_script("return document.body.scrollHeight")

        print("[INFO] Reached bottom of page. Waiting for ads to load...")
        time.sleep(3)

        fast = True

        if lite_mode == False:
            # Scroll back up
            if fast:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.8)
                print("[INFO] Returned to top of page.")
            else:
                print("[INFO] Scrolling back up to top...")
                while current_scroll > 0:
                    current_scroll -= step
                    if current_scroll < 0:
                        current_scroll = 0
                    driver.execute_script(f"window.scrollTo(0, {current_scroll});")
                    time.sleep(pause)

            print("[INFO] Returned to top of page.")
    except Exception as e:
        print(f"[WARN] Scroll operation failed: {e}")

def smart_scroll_page(driver, max_wait=10, step=500, pause=1.0, max_scrolls=100):
    import time
    """
    Smart scroll for pages with infinite scrolling.
    - Scrolls down gradually.
    - Waits for new content to load.
    - Stops if no new content appears after several attempts.
    """
    print("[INFO] Starting smart infinite scroll...")

    last_height = driver.execute_script("return document.body.scrollHeight")
    stable_count = 0
    scroll_count = 0

    while scroll_count < max_scrolls:
        scroll_count += 1
        driver.execute_script(f"window.scrollTo(0, {last_height});")
        time.sleep(pause)

        # Allow new content to load
        time.sleep(pause)

        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            stable_count += 1
            if stable_count >= max_wait:
                print(f"[INFO] No new content after {stable_count} checks. Stopping scroll.")
                break
        else:
            stable_count = 0  # reset when new content appears

        last_height = new_height

    print(f"[INFO] Finished scrolling. Total scrolls: {scroll_count}")
    # Scroll back to top to allow any above-the-fold ads to reload
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)

def unzip_profile(zip_path):
    import zipfile
    import tempfile
    
    tmp_dir = tempfile.mkdtemp(prefix="profileA_")

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)


    print(f"[INFO] Extracted profile to: {tmp_dir}")
    return tmp_dir

def unzip_profile_multi(zip_path, n):
    import zipfile
    import tempfile, shutil

    base_dirs = []

    for i in range(n):
        tmp_dir = tempfile.mkdtemp(prefix=f"profile_{i}_")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)
        base_dirs.append(tmp_dir)
        print(f"[INFO] Extracted profile #{i} to: {tmp_dir}")

    return base_dirs

def save_fullpage_screenshot(driver, output_file):
    """
    Save full page screenshot using Chrome DevTools Protocol (CDP)

    Args:
        driver: Selenium webdriver instance
        output_file: output png file path
    """

    # wait a bit for rendering/lazy load
    time.sleep(2)

    # get full page dimensions
    metrics = driver.execute_cdp_cmd(
        "Page.getLayoutMetrics",
        {}
    )

    width = metrics["contentSize"]["width"]
    height = metrics["contentSize"]["height"]

    # set virtual viewport
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {
            "mobile": False,
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
        },
    )

    # capture full page screenshot
    screenshot = driver.execute_cdp_cmd(
        "Page.captureScreenshot",
        {
            "format": "png",
            "captureBeyondViewport": True,
            "fromSurface": True,
        },
    )

    # save file
    with open(output_file, "wb") as f:
        f.write(base64.b64decode(screenshot["data"]))