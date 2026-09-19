from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, unquote
import tldextract
import csv
import os
import glob
import json

# ================= CONFIG =================

#1 - Round 1
#225 - Round 2
#397 - Round 3 - JP Test
#427 - Round 3
#495 - Round 4
#664 - Round 5
#875 - Round 6

# Các domain ads của Google cần giữ nguyên hostname
SPECIAL_ADS_HOSTS = {
    "doubleclick.net",
    "googlesyndication.com",
}

DOMAINS_EXCLUDES = ("theguardian.com", "bbc.com", "boston.com")

INVALID_START_PREFIXES = (
    "chrome-error://",
    "about:blank",
    "https://account.microsoft.com/privacy/ad-settings",
    "https://adssettings.google.com/whythisad?source",
    "https://advanced-store.com/en/data-privacy/",
    "https://app.adroll.com/optout/privacysandbox",
    "https://popup.taboola.com/",
    "https://privacy.as.criteo.com/adchoices",
    "javascript:",
    "mailto:",
    "tel:",
    "https://www.spotify.com/legal",
    "https://www.spotify.com/legal/privacy-policy/",
    "whatsapp://"
    "https://s0.2mdn.net/",
    "https://privacy.us.criteo.com/adchoices",
    "https://privacy.eu.criteo.com/adchoices",
    "https://pixel.quantcount.com",
    "https://economictimes.indiatimes.com",
    "https://m.economictimes.com",
    "https://www.dianomi.com/whatsthis",
    "https://www.google.com/url?ct=abg&q=https://www.google.com/adsense/support/bin/request",
    "https://support.google.com",
    "https://support.apple.com",
    "https://support.mozilla.org",
    "https://support.microsoft.com",
    "https://optout.",
    "https://legal.yahoo.com",

    "https://www.youtube.com",
    "https://youtu.be/"
    
    "https://youradchoices.com",
    
    "https://www.facebook.com/",
    "https://facebook.com/"
    
    "https://www.x.com/",
    "https://x.com",
    "https://twitter.com/",
    "https://www.twitter.com/",
    
    "https://yahoo.com/",
    "https://www.yahoo.com/",

    "https://www.instagram.com/",
    "https://instagram.com/",
    
    "https://www.tiktok.com/@",
    "https://tiktok.com/@",
    "https://www.huffpost.com/",
    "https://www.whatsapp.com/",
    "https://whatsapp.com/",
    "https://www.snapchat.com/",
    "https://snapchat.com/",
    "https://www.linkedin.com/",
    "https://linkedin.com/",
    "https://api.whatsapp.com/",
    "https://cloud.google.com",
    "https://advertising.bbcstudios.com/",
    "https://www.theguardian.com",
    "https://www.google.com/preferences/",
    "https://google.com/preferences/"
)

INVALID_END_PREFIXES = (
    "/privacy/",
    "/analytics.html"
    "privacy"
)

EXLCUDES = (
    {"guardian.co.uk": "guardian.com"},
    {"dailymail.co.uk": "dailymail.com"},
    {"huffingtonpost.com": "huffpost.com"},
    {"thetimes.co.uk": "thetimes.com"},
    {"bbci.co.uk": "bbc.com"},
    {"wired.com": "wired.co.uk"}
)

OUTPUT_GOOGLE = Path("google_ads_urls.csv")
OUTPUT_NON_GOOGLE = Path("non_google_ads_urls.csv")

# List domain of Google Ads
GOOGLE_AD_DOMAINS = [
    "googleadservices.com",
    "doubleclick.net",
    "googlesyndication.com",
]

SAFEFRAME_KEYWORDS = [
    "safeframe.googlesyndication.com",
    "/safeframe/",
]


def load_exclude_domains_file(csv_file: str) -> set:
    exclude_domains = set()

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            advertiser_url = row.get("advertiser_url", "")
            domain = extract_reached_domain(advertiser_url)
            if domain:
                exclude_domains.add(domain)

    return exclude_domains

def load_exclude_domains_folder(folder_path: str) -> set:
    exclude_domains = set()

    # lấy tất cả file .csv trong folder
    pattern = os.path.join(folder_path, "*.csv")
    csv_files = glob.glob(pattern)

    for file in csv_files:
        #print("Excluding file: ",file)
        with open(file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                advertiser_url = row.get("advertiser_url", "")
                domain = extract_reached_domain(advertiser_url)
                if domain:
                    exclude_domains.add(domain)

    return exclude_domains


def is_special_ads_host(host):
    if not host:
        return False
    return any(host.endswith(d) for d in SPECIAL_ADS_HOSTS)

def multi_decode(url, max_rounds=5):
    """
    Decode URL nhiều lần cho đến khi không đổi nữa
    """
    previous = url
    for _ in range(max_rounds):
        decoded = unquote(previous)
        if decoded == previous:
            break
        previous = decoded
    return previous


def extract_params_from_url(url):
    """
    Universal extractor:
    - Query parameters (?a=1&b=2)
    - Matrix parameters (;a=1;b=2)
    - Double/triple encoded URLs
    """

    all_params = []

    # 1️⃣ Decode nhiều vòng
    decoded_url = multi_decode(url)

    parsed = urlparse(decoded_url)

    # 2️⃣ Query parameters chuẩn
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    for k, v in query_params:
        all_params.append({"name": k, "value": v})

    # 3️⃣ Matrix parameters (;param=value)
    if ";" in parsed.path:
        parts = parsed.path.split(";")[1:]  # bỏ phần path đầu
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                all_params.append({"name": k, "value": v})

    return all_params

def extract_ads_domain(url):
    """
    ads_domain:
    - Google ads → giữ nguyên hostname
    - domain khác → eTLD+1
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if not host:
            return ""

        # Nếu là Google Ads / DoubleClick / Syndication
        if is_special_ads_host(host):
            return host

        # Ngược lại → eTLD+1
        ext = tldextract.extract(host)
        if not ext.domain or not ext.suffix:
            return host

        return f"{ext.domain}.{ext.suffix}"

    except Exception:
        return ""

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

def extract_domain(url):
    if not url:
        return ""

    try:
        ext = tldextract.extract(url)
        if not ext.domain or not ext.suffix:
            return ""
        return f"{ext.domain}"
    except Exception:
        return ""


def is_google_ads_domain(url: str) -> bool:
    try:
        hostname = urlparse(url).hostname or ""
        return any(
            hostname == d or hostname.endswith("." + d)
            for d in GOOGLE_AD_DOMAINS
        )
    except Exception:
        return False
    

def save_ads_csv(data_dict, output_file):
    with open(output_file,"w",newline="",encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ads_url",
            "screenshot_paths"
        ])
        for ads_url, screenshots in data_dict.items():
            writer.writerow([
                ads_url,
                json.dumps(
                    sorted(list(screenshots)),
                    ensure_ascii=False
                )
            ])

def save_selected_csv(data_dict, output_file, start_id):
    with open(output_file,"w",newline="",encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id_site",
            "ads_url",
            "screenshot_paths"
        ])

        for i, (ads_url, screenshots) in enumerate(data_dict.items(),start=start_id):
            writer.writerow([
                i,
                ads_url,
                json.dumps(
                    sorted(list(screenshots)),
                    ensure_ascii=False
                )
            ])
    
def is_safeframe(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""
        return (
            "safeframe.googlesyndication.com" in hostname
            or "/safeframe/" in path
        )
    except Exception:
        return False

def is_valid_url(url: str) -> bool:
    if not url:
        return False

    url = url.strip().lower()
    if url.startswith(INVALID_START_PREFIXES) or url.endswith(INVALID_END_PREFIXES):
        return False
    else:
        return True


def is_belong_to_google_ads_and_not_gclid(ads_url, host_dm):
    dec = False
    if is_valid_url(ads_url):
        if is_safeframe(ads_url):
            return False
        
        if is_google_ads_domain(ads_url):
            print("Google Ads URL: ",ads_url)
            has_gclid = False
            has_adurl = False
            params = extract_params_from_url(ads_url)
            for param in params:
                if param["name"].lower() == "gclid":
                    has_gclid = True
                    break
            for param in params:
                if param["name"].lower() == "adurl":
                    adu = param["value"].lower()
                    dm = extract_ads_domain(adu)
                    if dm == "" or dm == host_dm.lower():
                        has_adurl = False
                    else:
                        has_adurl = True
                    break

            if has_gclid==False and has_adurl==True:
                dec = True
        else:
            print("Non-Google Ads URL: ",ads_url)
    
    return dec