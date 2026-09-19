from libs.helpers import is_infinite_scroll_page, scroll_infinite, slow_scroll_page
from libs.captureAds import capture_marked_elements_lite
from libs.browser import init_browser
from libs.helpers import unzip_profile
from libs.internal import get_internal_links
import os, random



def performance_log_listener(driver, events, stop_event, after_flag,poll_interval=0.25, max_events=20000):
    import json, time
    from selenium.common.exceptions import WebDriverException

    while not stop_event.is_set():
        if len(events) >= max_events:
            break

        try:
            logs = driver.get_log("performance")
        except WebDriverException:
            break

        for entry in logs:
            if len(events) >= max_events:
                break
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method", "").startswith("Network."):
                    msg["_after"] = after_flag["value"]
                    events.append(msg)
            except Exception:
                continue

        time.sleep(poll_interval)


def stepsEachUrl_lite(driver, url, outdir, timeoutVisit=10):
    import time
    print(f"[INFO] Navigating to {url}...")
    
    driver.get(url)
    time.sleep(timeoutVisit)  # initial wait for page load


    js = """const style = document.createElement('style'); style.innerHTML = `#gateway-content,div[data-testid="gateway-content"] {display: none !important;visibility: hidden !important;opacity: 0 !important;} body {overflow: auto !important;}`;document.head.appendChild(style);"""
    driver.execute_script(js)


    if is_infinite_scroll_page(driver):
        print("[INFO] Page detected as INFINITE SCROLL.")
        scroll_infinite(driver,lite_mode=True)
    else:
        print("[INFO] Page is NORMAL scroll.")
        slow_scroll_page(driver,lite_mode=True)

    time.sleep(5)
    
    capture_marked_elements_lite(driver, outdir=outdir)



def create_driver(profile_zip, headless, extension_unpacked_folder=None, page_load_strategy="normal"):
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent
    if extension_unpacked_folder is None:
        EXT_PATH = BASE_DIR / "extensions" / "DetectAds"
    else:
        EXT_PATH = BASE_DIR / "extensions" / extension_unpacked_folder
    EXT_PATH = str(EXT_PATH)
    
    profile_dir = unzip_profile(profile_zip)

    try:
        driver = init_browser(user_data_dir=profile_dir,headless=headless, extension_unpacked_folder=EXT_PATH, page_load_strategy=page_load_strategy)
    except Exception as e:
        print(f"[Error - Try Again...] {e}")
        try:
            driver = init_browser(user_data_dir=profile_dir,headless=headless, extension_unpacked_folder=EXT_PATH, page_load_strategy=page_load_strategy)
        except Exception as e:
            raise

    return [driver, profile_dir]




def runTest_lite(driver, target_url, outdir, max_Pages, timeoutVisit):
    site = target_url.replace("https://", "").replace("http://","").replace("/","_")
    outdir_target = os.path.join(outdir, site)
    os.makedirs(outdir_target, exist_ok=True)

    visited = set()
    stepsEachUrl_lite(driver, target_url, outdir_target, timeoutVisit=timeoutVisit)
        
    visited.add(driver.current_url)
    pool = get_internal_links(driver, driver.current_url)

    if not pool:
        print("No internal links found.")
        return

    print(f"Found {len(pool)} internal links.")
    random.shuffle(pool)

    for url in pool:
        if len(visited) >= max_Pages:
            break

        if url in visited:
            continue

        print(f"[MASTER] Visiting next URL: {url}")
        try:
            stepsEachUrl_lite(driver, url, outdir_target, timeoutVisit=timeoutVisit)
        except Exception as e:
            print(f"[WARN] Failed to process {url}: {e}")

        visited.add(url)
    print(f"Finished visiting {len(visited)} pages.")
