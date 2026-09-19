import threading
import os, time
from libs.helpers import loadSites
from libs.browser import close_and_delete_profile
from libs.process import create_driver, runTest_lite
from bannerclick import bannerdetectionUpd as bc
from urllib.parse import urlparse
import argparse, random
from datetime import datetime
from pathlib import Path
from selenium.common.exceptions import WebDriverException
import sys


parser = argparse.ArgumentParser(description="Ads crawler")
parser.add_argument("--sites", required=True,help="Path to the file containing the list of sites to crawl")
parser.add_argument("--country", required=True, help=f"Country code")
parser.add_argument("--profile-zip",required=True,help=("Name of the Chrome profile ZIP file to use. The file must exist inside the default 'profiles/' directory. "))
parser.add_argument("--begin", type=int, default=None, help="Start index in sites list (0-based)")
parser.add_argument("--end", type=int, default=None, help="End index (exclusive)")
parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
parser.add_argument("--max-pages",type=int, default=1, help="Maximum number of pages to crawl (including target URL)")
parser.add_argument("--timeout-visit", type=int, default=60, help="Page visit timeout (seconds)")
parser.add_argument("--run-no", type=int, default=0, help="Run number for the same domain per round (default: 0)")
parser.add_argument("--auto-run", type=int, default=0, help="Run auto (default: 0)")


args = parser.parse_args()

country = args.country
print(f"[INFO] Running crawler for country: {country}")
run_no = args.run_no
base_dir = f"captures"

def createDir(base_dir, country, run_num):
    date_str = datetime.now().strftime("%d%m")
    rand_5 = random.randint(10000, 99999)

    outdir = f"{base_dir}/{country}_{date_str}_run{run_num}_{rand_5}"
    os.makedirs(outdir, exist_ok=False)
    print(f"[INFO] Output directory: {outdir}")
    return outdir


#profiles_zip = "profiles/train_MOD.zip"

BASE_DIR = Path(__file__).resolve().parent
PROFILES_DIR = BASE_DIR / "profiles"
if not PROFILES_DIR.is_dir():
    raise RuntimeError(f"'profiles/' directory does not exist: {PROFILES_DIR}")
profile_name = args.profile_zip
# Allow user to pass with or without .zip
if not profile_name.endswith(".zip"):
    profile_name += ".zip"

profiles_zip = PROFILES_DIR / profile_name

# ZIP must exist
if not profiles_zip.is_file():
    raise RuntimeError(f"Profile ZIP not found: {profiles_zip}")

profiles_zip = str(profiles_zip)

print(f"[INFO] Using profile ZIP: {profiles_zip}")

headless = args.headless
max_Pages = args.max_pages         # Including the target_url
timeoutVisit = args.timeout_visit

choice_banner = 1




listSites = loadSites(args.sites)
total_sites = len(listSites)
begin = args.begin
end = args.end

if begin is not None and begin < 0:
    raise ValueError("begin must be >= 0")

if end is not None and end > total_sites:
    end = total_sites

if begin is not None and end is not None and begin >= end:
    raise ValueError("begin must be < end")


if begin is None and end is None:
    selected_sites = listSites
elif begin is not None and end is None:
    selected_sites = listSites[begin:]
elif begin is None and end is not None:
    selected_sites = listSites[:end]
else:
    selected_sites = listSites[begin:end]

print(
    f"[INFO] Loaded {total_sites} sites, "
    f"processing {len(selected_sites)} sites "
    f"(begin={begin}, end={end})"
)

def watchdog(driver_ref, domain):
    """ Kills the driver if it takes too long on a domain. """
    start_time = time.time()
    WATCHDOG_TIMEOUT = 60 * 12  # 12 minutes
    while time.time() - start_time < WATCHDOG_TIMEOUT:
        time.sleep(1)  # Check every second
        if driver_ref["done"]:  # If main thread finished, exit watchdog
            return

    # If execution time exceeds timeout, kill driver and restart
    print(f"{domain} is stuck! Forcing driver restart...")
    try:
        driver_ref["driver"].quit()  # Kill Selenium driver
    except:
        pass  # Ignore errors if already closed
    driver_ref["restart"] = True  # Signal main thread to restart driver


print(f"[INFO] Creating browser driver...")
try:
    init = create_driver(profiles_zip, headless)
    driver = init[0]
    profile_dir = init[1]
except Exception as e:
    print(f"[Error] {e}")
    sys.exit(0)

print(f"[INFO] Browser driver created.")

driver_ref = {"driver": driver, "done": False, "restart": False}

autorun = args.auto_run

if run_no != 0:
    start_run = run_no
    autorun = run_no
else:
    if autorun != 0:
        start_run = 1
    else:
        start_run = 1
        autorun = 1

for i in range(start_run, autorun + 1):
    print(f"Run no {i}...")
    outdir = createDir(base_dir, country, i)
    for site in selected_sites:
        driver_ref["restart"] = False
        driver_ref["done"] = False
        watchdog_thread = threading.Thread(target=watchdog, args=(driver_ref, site))
        watchdog_thread.start()
    
        try:
            print("====================================="*3)
            dir_bc = "/bannerclick/" + site.replace("https://","").replace("http://","").replace("/","_") + "/"
            outdir_bc = "./" + outdir + dir_bc

            print(f"Running for site: {site}")
            domain = urlparse(site).netloc

            has_banner = bc.run_ONE_pc_AdsCrawler(driver = driver, choice = choice_banner, domain = domain, url=site, dir_bc = outdir_bc)

            runTest_lite(driver, site, outdir, max_Pages, timeoutVisit)
            print(f"=========================")
            time.sleep(2)
        
            driver_ref["done"] = True
        except WebDriverException as e:
            print(f"WebDriver Error: {e}. Restarting Chrome...")
            driver_ref["restart"] = True
        except Exception as e:
            print(f"[ERROR] An error occurred while processing site {site}: {e}")
            driver_ref["restart"] = True
        finally:
            driver_ref["done"] = True

        watchdog_thread.join()
        if driver_ref["restart"]:
            print(f"[INFO] Restarting browser driver...")
            try:
                close_and_delete_profile(driver, profile_dir)
            except:
                pass

            try:
                init = create_driver(profiles_zip)
                driver = init[0]
                profile_dir = init[1]
            except:
                time.sleep(10)
                init = create_driver(profiles_zip)
                driver = init[0]
                profile_dir = init[1]
            print(f"[INFO] Browser driver created.")
            driver_ref["driver"] = driver
    
        time.sleep(5)  # Brief pause between sites

    else:
        print(f"End of run no {i}")
        time.sleep(5)

else:
    print("[INFO] All sites processed.")
    time.sleep(2)
    close_and_delete_profile(driver, profile_dir)
