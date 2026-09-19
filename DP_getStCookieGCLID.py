from urllib.parse import urlparse, parse_qsl, unquote
import tldextract
import csv
from libs.dbProcess import get_db_conn
import os
import hashlib
import base64
import urllib.parse


def generate_encoded_values(value: str):
    encoded_values = set()

    # plaintext
    encoded_values.add(value)

    # md5
    encoded_values.add(hashlib.md5(value.encode()).hexdigest())

    # sha1
    encoded_values.add(hashlib.sha1(value.encode()).hexdigest())

    # sha256
    encoded_values.add(hashlib.sha256(value.encode()).hexdigest())

    # sha512
    encoded_values.add(hashlib.sha512(value.encode()).hexdigest())

    # base64
    encoded_values.add(base64.b64encode(value.encode()).decode())
    
    # URL encode
    encoded_values.add(urllib.parse.quote(value))
    
    # Hex:
    encoded_values.add(value.encode().hex())

    return encoded_values


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

def get_data_cookies_by_id_csv(conn, value, id_csv, country, choice):
    #values = generate_encoded_values(value)
    #conditions = []
    #for v in values:
    #    conditions.append(f"value LIKE '%{v}%'")
    #where_clause = " OR ".join(conditions)

    curr = conn.cursor()

    query = f"""
        SELECT run_no, name, value, domain, current_url
        FROM cookies 
        WHERE id_csv = {id_csv} AND country = '{country}' AND choice={choice} AND (value LIKE '%{value}%')
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


def check_exist(data):
    run_no = set()
    if data:
        for row in data:
            reached_url = row[4]
            domain_cookie = row[3]
            reached_domain = extract_reached_domain(reached_url)
            if is_first_party(domain_cookie, reached_domain):
                run_no.add(row[0])
    
    return run_no

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



def extract_params_from_url(url):
    """
    Universal extractor:
    - Query parameters (?a=1&b=2)
    - Matrix parameters (;a=1;b=2)
    - Double/triple encoded URLs
    """

    all_params = []

    decoded_url = multi_decode(url)

    parsed = urlparse(decoded_url)

    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    for k, v in query_params:
        all_params.append({"name": k, "value": v})


    if ";" in parsed.path:
        parts = parsed.path.split(";")[1:]  # bỏ phần path đầu
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                all_params.append({"name": k, "value": v})

    return all_params

def standard_OLD(run_no, na=False):
    max_run = 5

    if na:
        result = tuple(
            "na"
            for i in range(1, max_run + 1)
        )
    else:
        result = tuple(
            "yes" if i in run_no else "no"
            for i in range(1, max_run + 1)
        )
    return result

def standard(run_no, run_has_consent):
    max_run = 5

    def normalize(runs):
        return {(i - 1) % max_run + 1 for i in runs}
    
    run_no_norm = normalize(run_no)
    run_has_consent_norm = normalize(run_has_consent)

    return tuple(
        "yes" if i in run_no_norm else "no"
        if i in run_has_consent_norm
        else "NA"
        for i in range(1, max_run + 1)
    )

def for_each_country_case(output_csv, country, choice):
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
        
        params = extract_params_from_url(ads_url)
        value_gclid = None
        for p in params:
            if p["name"].lower() == "gclid":
                value_gclid = p["value"]
                #print(value_gclid)
                break
        
        if value_gclid:
            with get_db_conn() as conn:
                data = get_data_cookies_by_id_csv(conn, value_gclid, id_csv, country, choice)
            
            run_no = check_exist(data)
            run_no_res = standard(run_no, run_has_consent) 
            results.append({
                "id_csv": id_csv,
                "gg_ads_url": ads_url,
                "advertiser_url": advertiser_url,
                "run_1": run_no_res[0],
                "run_2": run_no_res[1],
                "run_3": run_no_res[2],
                "run_4": run_no_res[3],
                "run_5": run_no_res[4],
            })
        
        else:
            results.append({
                "id_csv": id_csv,
                "gg_ads_url": ads_url,
                "advertiser_url": advertiser_url,
                "run_1": "KO",
                "run_2": "KO",
                "run_3": "KO",
                "run_4": "KO",
                "run_5": "KO",
            })
    
    import csv

    results = deduplicate(results)

    fieldnames = ["id_csv", "gg_ads_url", "advertiser_url", "run_1", "run_2", "run_3", "run_4", "run_5"]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()   # ghi header
        writer.writerows(results)  # ghi data

def has_consent_banner(conn, id_csv, country, choice):
    curr = conn.cursor()

    query = f"""
        SELECT DISTINCT run_no
        FROM consent_banners WHERE id_csv = {id_csv} AND country = '{country}' AND choice = {choice}
    """
    
    curr.execute(query)
    data = curr.fetchall()
    run_no = set()
    for row in data:
        run_no.add(row[0])
    return run_no

def main(outdir, country):
    choices = [0,1,2]
    for choice in choices:
        if choice == 0:
            txtch = "no-interaction"
        elif choice == 1:
            txtch = "accept-all"
        elif choice == 2:
            txtch = "reject-all"

        output_csv = f"{outdir}/1st_party_cookie_{country}_{txtch}.csv"
        for_each_country_case(output_csv, country, choice)


if __name__ == "__main__":
    outdir = f"Report_1stPartyCookie"
    country = input("Input country code: ")

    os.makedirs(outdir, exist_ok=True)
    main(outdir, country)