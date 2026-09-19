import threading
import os, time
from libs.browser import init_browser
from bannerclick import bannerdetectionUpd as bc
from urllib.parse import urlparse
import argparse, random
from datetime import datetime
from pathlib import Path
from selenium.common.exceptions import WebDriverException
import csv
from libs.dbProcess import get_db_conn, insert_site_visitedAds
from libs.getStorage import clear_all_storage
import requests
from libs.cleanup import cleanup_driver
import sys

def getidDir(base_dir, country, date_str):
    while True:
        idDir = random.randint(10000, 99999)
        exists = Path(f"{base_dir}/{country}_{date_str}_visitedURL_{idDir}").is_dir()
        if not exists:
            return idDir

def get_ip_country():
    try:
        response = requests.get("https://ipinfo.io/json", timeout=10)
        response.raise_for_status()
        data = response.json()

        ip = data.get("ip")
        country = data.get("country")

        return ip, country

    except requests.RequestException as e:
        print(f"Error: {e}")
        return None, None

def watchdog(driver_ref, id_site):
    """ Kills the driver if it takes too long on a domain. """
    start_time = time.time()
    WATCHDOG_TIMEOUT = 60 * 20  # 20 minutes
    while time.time() - start_time < WATCHDOG_TIMEOUT:
        time.sleep(1)  # Check every second
        if driver_ref["done"]:  # If main thread finished, exit watchdog
            return

    # If execution time exceeds timeout, kill driver and restart
    print(f"{id_site} is stuck! Forcing driver restart...")


    stop_event = driver_ref.get("stop_event")
    listener = driver_ref.get("listener")

    if stop_event is not None:
        stop_event.set()
    if listener is not None:
        listener.join(timeout=3)
    
    driver_ref["restart"] = True  # Signal main thread to restart driver

    driver = driver_ref.get("driver")
    cleanup_driver(driver=driver)

CHOICES = [0,2,1]

parser = argparse.ArgumentParser(description="Ads crawler")
parser.add_argument("--sites", required=True,help="Path to the file containing the list of sites to crawl")
parser.add_argument("--country", required=True, help=f"Country code")
parser.add_argument("--begin", type=int, default=None, help="Start index in sites list (0-based)")
parser.add_argument("--end", type=int, default=None, help="End index (exclusive)")
parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
#parser.add_argument("--choice-banner",type=int,choices=[0, 1, 2],default=1,help="Cookie banner interaction: 0=no interaction, 1=accept (default), 2=reject")
parser.add_argument("--run-no", type=int, required=True, help="Run number")

args = parser.parse_args()

country = args.country
print(f"[INFO] Running visit Ads URLs for country: {country}")

date_str = datetime.now().strftime("%d%m")
base_dir = "capturesURL"

idDir = getidDir(base_dir, country, date_str)

outdir = f"{base_dir}/{country}_{date_str}_visitedURL_{idDir}"
os.makedirs(outdir, exist_ok=False)

print(f"[INFO] Output directory: {outdir}")

#profiles_zip = "profiles/train_MOD.zip"

BASE_DIR = Path(__file__).resolve().parent
headless = args.headless
#choice_banner = args.choice_banner  # or interact_mode: 0. no interaction 1.accept 2.reject
ip, tcountry_ = get_ip_country()


def loadSitesFromCSV(csv_path):
    sites = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sites.append({
                "id_site": int(row["id_site"]),
                "url": row["ads_url"]
            })
    return sites


listSites = loadSitesFromCSV(args.sites)
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
    f"[INFO] Loaded {total_sites} urls, "
    f"processing {len(selected_sites)} urls "
    f"(begin={begin}, end={end})"
)

def work_once(choice_banner, run_no, listSites, err=False):
    driver = None
    for attemp in range(3):
        try:  
            driver = init_browser(headless=headless)
            break
        except KeyboardInterrupt:
            cleanup_driver(driver=driver)
            sys.exit(0)
        except Exception as e:
            print(f"Error in create driver: {e} \nTry again")
            time.sleep(5)

    if driver is None:
        raise RuntimeError("Cannot create driver")

    print(f"[INFO] Browser driver created.")

    driver_ref = {"driver": driver, "done": False, "restart": False, "stop_event": None, "listener": None}
    listError = []
    idError = set()

    for idx, site in enumerate(listSites, start=1):
        _erMessage = ""
        print(
            f"[INFO] Site {idx}/{len(listSites)} "
            f"(id_csv={site['id_site']})"
        )

        id_csv = site['id_site']
        url = site['url']
        domain = urlparse(url).netloc

        driver_ref["restart"] = False
        driver_ref["done"] = False
        driver_ref["stop_event"] = None
        driver_ref["listener"] = None

        watchdog_thread = threading.Thread(target=watchdog, args=(driver_ref,id_csv))
        watchdog_thread.start()
        with get_db_conn() as conn:
            id_site = insert_site_visitedAds(conn, domain_url = url, id_csv=id_csv, ip=ip, country=country, run_no=run_no, choice=choice_banner, status="error")

        url_reached = ""

        try:
            driver.get("about:blank")
            clear_all_storage(driver)
            print("Cleared cookie & cache!")
            time.sleep(5)

            print("==============="*3)
            dir_bc = "/bannerclick/" + str(id_site) + "/"
            outdir_bc = "./" + outdir + dir_bc
            print(f"Running for url: {url}")
            has_banner = bc.run_ONE_pc_nonDB(driver = driver, driver_ref=driver_ref, choice = choice_banner, domain = domain, url=url, headless=headless, dir_bc = outdir_bc, id_site=id_site, id_csv=id_csv, country=country, run_no=run_no)
            time.sleep(6)
            url_reached = driver.current_url

            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE sites SET reached_url=%s, crawl_status='success' WHERE id_site=%s""", (url_reached, id_site))

            driver_ref["done"] = True
        except KeyboardInterrupt:
            cleanup_driver(driver)
            sys.exit(0)
        except WebDriverException as e:
            _erMessage = f"WebDriver Error: {e}"
            print(_erMessage)
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE sites SET crawl_status='error', error_message=%s WHERE id_site=%s""", (_erMessage, id_site))

            if "ERR_NAME_NOT_RESOLVED" in str(e) or "ERR_CONNECTION_CLOSED" in str(e):
                if err==False and site['id_site'] not in idError:
                    site_err = {"id_site": site['id_site'], "url": site['url']}
                    listError.append(site_err)
                    idError.add(site['id_site'])
                stop_event = driver_ref.get("stop_event")
                listener = driver_ref.get("listener")

                if stop_event is not None:
                    stop_event.set()
                if listener is not None:
                    listener.join(timeout=3)

                driver_ref["done"] = True
            else:
                driver_ref["restart"] = True
        except Exception as e:
            _erMessage = f"Error: {e}"
            print(_erMessage)
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE sites SET crawl_status='error', error_message=%s WHERE id_site=%s""", (_erMessage, id_site))

            if "Max retries exceeded" in str(e):
                if err==False and site['id_site'] not in idError:
                    site_err = {"id_site": site['id_site'], "url": site['url']}
                    listError.append(site_err)
                    idError.add(site['id_site'])

                stop_event = driver_ref.get("stop_event")
                listener = driver_ref.get("listener")
                if stop_event is not None:
                    stop_event.set()
                if listener is not None:
                    listener.join(timeout=3)

                driver_ref["done"] = True
            else:
                driver_ref["restart"] = True
        finally:
            driver_ref["done"] = True
    
        watchdog_thread.join()
        if driver_ref["restart"]:
            if err == False and site['id_site'] not in idError:
                site_err = {"id_site": site['id_site'], "url": site['url']}
                listError.append(site_err)
                idError.add(site['id_site'])

            print(f"[INFO] Restarting browser driver...")
            time.sleep(2)
            stop_event = driver_ref.get("stop_event")
            listener = driver_ref.get("listener")
            if stop_event is not None:
                stop_event.set()
            if listener is not None:
                listener.join(timeout=3)

            cleanup_driver(driver=driver)
            driver = None

            for attemp in range(3):
                try:
                    driver = init_browser(headless=headless)
                    break
                except Exception as e:
                    print(f"Error in create driver: {e} \nTry again")
                    time.sleep(5)

            if driver is None:
                raise RuntimeError("Cannot create driver!")

            print(f"[INFO] Browser driver created.")
            driver_ref["driver"] = driver
                   
        time.sleep(5)  # Brief pause between sites

    else:
        print("[INFO] All Ads URL processed.")
        time.sleep(10)
        cleanup_driver(driver=driver)

    if len(listError)>0 :
        work_once(choice_banner, run_no, listError, err=True)


for choice in CHOICES:
    print(f"Start choice {choice} - run no {args.run_no}.")
    work_once(choice, args.run_no, selected_sites)
    print(f"Finished run no {args.run_no}. Sleep 60s")
    time.sleep(30)
