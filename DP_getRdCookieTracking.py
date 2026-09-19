from urllib.parse import urlparse, parse_qsl, unquote
import tldextract
import csv
from libs.dbProcess import get_db_conn
import pandas as pd
import os
import argparse


def load_justdomains_from_folder(folder_path):
    domains_set = set()

    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            file_path = os.path.join(folder_path, filename)

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    domain = line.strip()
                    if domain:  # bỏ dòng trống
                        domains_set.add(domain)

    return list(domains_set)


def deduplicate(results):
    seen = set()
    output = []

    for row in results:
        id_csv = row["id_csv"]
        domain = extract_reached_domain(row["advertiser_url"])
        key = (id_csv, domain)
        if key not in seen:
            seen.add(key)
            output.append(row)

    return output


def multi_decode(url, max_rounds=5):
    previous = url
    for _ in range(max_rounds):
        decoded = unquote(previous)
        if decoded == previous:
            break
        previous = decoded
    return previous

def loadSitesFromCSV(csv_path):
    sites = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sites.append({
                "id_csv": int(row["id_site"]),
                "url": row["ads_url"]
            })
    return sites


def is_first_party(cookie_domain, advertiser_domain):
    cookie_domain = str(cookie_domain).lstrip(".")
    if cookie_domain == advertiser_domain:
        return True

    if cookie_domain.endswith("." + advertiser_domain):
        return True

    return False

def get_data_cookies_by_id_csv(conn, id_csv, country, choice):
    curr = conn.cursor()

    query = f"""
        SELECT run_no, name, value, domain, current_url
        FROM cookies 
        WHERE id_csv = {id_csv} AND country='{country}' AND choice={choice} AND is_after = True
    """
    
    curr.execute(query)
    data = curr.fetchall()
    return data


def get_data_sites(conn, country, choice):
    curr = conn.cursor()

    query = f"""
        SELECT DISTINCT id_csv, domain_url, reached_url
        FROM sites
        WHERE crawl_status = 'success' AND country = '{country}' AND choice = {choice}
    """
    
    curr.execute(query)
    data = curr.fetchall()
    return data




def check_exist(data, justdomains):
    run_no = []
    domain_checked = set()
    if data:
        for row in data:
            reached_url = row[4]
            domain_cookie = row[3]
            reached_domain = extract_reached_domain(reached_url)
            if is_first_party(domain_cookie, reached_domain) == False:
                d_cookie = str(domain_cookie).lstrip(".").lower()
                if d_cookie in justdomains:
                    run_no.append(row[0])
                    domain_checked.add((row[0], d_cookie))
    
    return run_no, domain_checked

def extract_reached_domain(url):
    if not url:
        return ""

    try:
        ext = tldextract.extract(url)
        if not ext.domain or not ext.suffix:
            return ""
        return f"{ext.domain}.{ext.suffix}"
    except Exception:
        return ""

def standard_unique(run_no, run_has_consent):
    max_run = 5

    def normalize(runs):
        result = set()
        for run in runs:
            new_run = (run[0] - 1) % max_run + 1
            result.add((new_run, run[1]))
        return result
    
    def normalize_consent(runs):
        return {(i - 1) % max_run + 1 for i in runs}
    
    run_no_norm = normalize(run_no)
    run_consent_norm = normalize_consent(run_has_consent)
    
    # group domain theo run
    run_to_domains = {}
    for run, domain in run_no_norm:
        if run not in run_to_domains:
            run_to_domains[run] = set()
        run_to_domains[run].add(domain)

    # build kết quả
    result = []
    for i in range(1, max_run + 1):
        if i not in run_consent_norm:
            result.append("N/A")
        else:
            result.append(len(run_to_domains.get(i, set())))

    return tuple(result)

def standard(run_no, run_has_consent):
    max_run = 5

    def normalize(runs):
        return [(i - 1) % max_run + 1 for i in runs]
    
    run_no_norm = normalize(run_no)
    run_has_consent_norm = normalize(run_has_consent)

    return tuple(
        run_no_norm.count(i) if i in run_no_norm else 0
        if i in run_has_consent_norm
        else "N/A"
        for i in range(1, max_run + 1)
    )

def for_each_country_case(output_csv, country, choice, justdomains):
    results = []
    with get_db_conn() as conn:
        data_sites = get_data_sites(conn, country, choice)
    
    for row_site in data_sites:
        id_csv = row_site[0]
                
        ads_url = row_site[1]
        advertiser_url = row_site[2]


        if choice == 0:
            run_has_consent = set()
            max = 100
            for i in range(1, max+1):
                run_has_consent.add(i)
        else:
            with get_db_conn() as conn:
                run_has_consent = has_consent_banner(conn, id_csv, country, choice)
            

        with get_db_conn() as conn:
            data = get_data_cookies_by_id_csv(conn, id_csv, country, choice)
            
        run_no, domain_checked = check_exist(data, justdomains)
        run_no_res = standard(run_no, run_has_consent)
        run_no_unique_res = standard_unique(domain_checked, run_has_consent)
        results.append({
            "id_csv": id_csv,
            "gg_ads_url": ads_url,
            "advertiser_url": advertiser_url,
            "run_1": run_no_res[0],
            "run_2": run_no_res[1],
            "run_3": run_no_res[2],
            "run_4": run_no_res[3],
            "run_5": run_no_res[4],
            "unique_run_1": run_no_unique_res[0],
            "unique_run_2": run_no_unique_res[1],
            "unique_run_3": run_no_unique_res[2],
            "unique_run_4": run_no_unique_res[3],
            "unique_run_5": run_no_unique_res[4],
        })

    
    import csv

    results = deduplicate(results)

    fieldnames = ["id_csv", "gg_ads_url", "advertiser_url", "run_1", "run_2", "run_3", "run_4", "run_5", "unique_run_1", "unique_run_2", "unique_run_3", "unique_run_4", "unique_run_5"]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

def has_consent_banner(conn, id_csv, country, choice):
    curr = conn.cursor()

    query = f"""
        SELECT DISTINCT run_no
        FROM consent_banners WHERE id_csv = {id_csv}  AND country = '{country}' AND choice = {choice}
    """
    
    curr.execute(query)
    data = curr.fetchall()
    run_no = set()
    for row in data:
        run_no.add(row[0])
    return run_no

def main(outdir, country):
    choices = [0,1,2]
    justDomains = load_justdomains_from_folder("justdomains")
    for choice in choices:
        if choice == 0:
            txtch = "no-interaction"
        elif choice == 1:
            txtch = "accept-all"
        elif choice == 2:
            txtch = "reject-all"
    
        output_csv = f"{outdir}/3rd_party_trackingcookie_{country}_{txtch}.csv"
        for_each_country_case(output_csv, country, choice, justdomains=justDomains)

if __name__ == "__main__":
    outdir = f"Report_3rdPartyTrackingCookie"
    country = input("Input country code: ")

    os.makedirs(outdir, exist_ok=True)
    main(outdir, country)