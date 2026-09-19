#!/usr/bin/env python3
import os
import time
import tempfile
import shutil
import sys
import argparse
from pathlib import Path

from libs.browser import init_browser
from libs.helpers import loadSites, is_infinite_scroll_page, scroll_infinite, slow_scroll_page


def parse_args():
    parser = argparse.ArgumentParser(description="Train Chrome profile with Detect Ads extension")
    parser.add_argument("--training-sites", required=True, help="Path to the file containing the list of sites to visit for training")
    parser.add_argument("--page-wait",type=int, default=90, help="Seconds to wait after each page load (default: 90)")
    parser.add_argument("--headless", action="store_true",help="Run browser in headless mode")
    parser.add_argument("--output-name", required=True, help="Output zip filename (without .zip). Saved inside profiles/ (default: training)")
    return parser.parse_args()

# ==== CONFIG ====

POST_QUIT_WAIT_SECONDS = 10
BASE_DIR = Path(__file__).resolve().parent

EXT_PATH = BASE_DIR / "extensions" / "DetectAds"
EXT_PATH = str(EXT_PATH)

# ==================

def main():
    args = parse_args()
    training_sites = args.training_sites
    page_wait = args.page_wait
    headless = args.headless
    output_name = args.output_name

    # profiles dir
    PROFILES_DIR = BASE_DIR / "profiles"
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # zip basename (NOT INCLUDE .zip)
    zip_basepath = PROFILES_DIR / output_name

    sites = loadSites(training_sites)

    print("[+] Config:")
    print(f"    - training_sites = {training_sites}")
    print(f"    - page_wait      = {page_wait} seconds")
    print(f"    - headless       = {headless}")
    print(f"    - output zip     = {zip_basepath}.zip")

    temp_profile_dir = tempfile.mkdtemp(prefix="uc_manual_ext_profile_")
    print(f"[+] Temporary profile directory: {temp_profile_dir}")

    driver = None
    try:
        print("[+] Starting initialize Chrome profile ...")
        driver = init_browser(user_data_dir=temp_profile_dir, extension_unpacked_folder=EXT_PATH, headless=headless)
        time.sleep(1)  # give it a little time
        
        print("[+] Visiting training sites ...")
        try:
            for url in sites:
                print(f"[INFO] Navigating to {url}")
                try:
                    driver.get(url)
                except Exception as e:
                    print(f"[WARN] Exception on driver.get({url}): {e}")
                    continue
                # Wait for network + resources to load; tune as needed
                time.sleep(3)
                
                
                # Attempt light scrolling to trigger lazy-loaded ads/scripts/resources
                if is_infinite_scroll_page(driver):
                    print("[INFO] Page detected as INFINITE SCROLL.")
                    scroll_infinite(driver)
                else:
                    print("[INFO] Page is NORMAL scroll.")
                    slow_scroll_page(driver)

                # final wait
                time.sleep(page_wait)

            print("[INFO] Done visiting sites. Closing browser...")
        except:
            pass
        print("[+] Closing Chrome ...")
        try:
            driver.quit()
        except Exception as e:
            print("[!] Error:", e)
        finally:
            driver = None

        # đợi để file system commit
        time.sleep(POST_QUIT_WAIT_SECONDS)

        # Create zip (shutil.make_archive concat .zip)
        print(f"[+] Zipping temporary profile ... -> {zip_basepath}.zip ...")
        archive_path = shutil.make_archive(str(zip_basepath), 'zip', temp_profile_dir)
        print(f"[+] Created zip: {archive_path}")

    except KeyboardInterrupt:
        print("\n[!] Canceled by user (KeyboardInterrupt).")
        if driver:
            try:
                driver.quit()
            except:
                pass
    except Exception as exc:
        print("[!] Error occurred:", exc)
        if driver:
            try:
                driver.quit()
            except:
                pass
        # If an error occurred, keep the temp profile for debugging
        print(f"[!] Temporary profile saved at: {temp_profile_dir} for debug.")
        sys.exit(1)
    else:
        # If we reach here, everything was successful
        try:
            print("[+] Deleting temporary profile folder...")
            shutil.rmtree(temp_profile_dir)
            print("[+] Deleted temporary profile folder.")
        except Exception as e:
            print("[!] Cannot delete temporary profile folder:", e)
            print(f"[!] Temporary profile folder still exists at: {temp_profile_dir}")
    
    print("\nFinished. File zip of your profile with the extension:")
    print(f" -> {os.path.abspath(archive_path)}")
    print("You can unzip and reuse this profile (e.g., copy into user-data-dir when needed).")

if __name__ == "__main__":
    main()
