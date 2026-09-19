from pathlib import Path
from urllib.parse import urlparse, parse_qsl, unquote
import tldextract
import csv

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



def is_special_ads_host(host):
    if not host:
        return False
    return any(host.endswith(d) for d in SPECIAL_ADS_HOSTS)

def multi_decode(url, max_rounds=5):
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

def extract_ads_domain(url):
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if not host:
            return ""

        if is_special_ads_host(host):
            return host

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

def collect_ads_by_country():
    list_ads_url = set()
    list_gg_ads = set()
    list_gg_ads_gclid = set()
    unique_pair = set()
    list_selected_url = set()

    for run_dir in ROOT_DIR.iterdir():
        for site_dir in run_dir.iterdir():
            sitename = site_dir.name
            if sitename == "bannerclick":
                continue
            siteDomain = extract_reached_domain(sitename)

            ads_file = site_dir / "Ads_URL.txt"
            if not ads_file.exists():
                continue

            with open(ads_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ads_url, screenshot_path = line.rsplit(",", 1)
                        ads_url = ads_url.strip()
                        screenshot_path = screenshot_path.strip()
                    except ValueError:
                        ads_url = line.strip()
                        screenshot_path = ""


                    # ads_url = line.strip()
                    adsUrlDomain = extract_reached_domain(ads_url)
                    if adsUrlDomain == "" or siteDomain.lower() == adsUrlDomain.lower() or adsUrlDomain in DOMAINS_EXCLUDES:
                        continue

                    adsUrlDomain = extract_domain(ads_url)
                    siteDomain = extract_domain(sitename)
                    if adsUrlDomain == "" or siteDomain.lower() == adsUrlDomain.lower():
                        continue
                    
                    if is_valid_url(ads_url):
                        if is_safeframe(ads_url):
                            continue

                        list_ads_url.add(ads_url)

                        if is_google_ads_domain(ads_url):
                            has_gclid = False
                            has_adurl = False
                            advertiser_url = None
                            
                            params = extract_params_from_url(ads_url)
                            for p in params:
                                if p["name"].lower() == "gclid":
                                    has_gclid = True
                                    break
                                    
                            
                            for p in params:
                                if p["name"].lower() == "adurl":
                                    has_adurl = True
                                    advertiser_url = p["value"]
                                    break
                            
                            if has_adurl and has_gclid:
                                list_gg_ads_gclid.add(ads_url)
                                ads_domain = extract_ads_domain(ads_url)
                                advertiser_domain = extract_reached_domain(advertiser_url)
                                


                                pair = (ads_domain,advertiser_domain)
                                if pair not in unique_pair:
                                    unique_pair.add(pair)
                                    list_selected_url.add(ads_url)


                            list_gg_ads.add(ads_url)


    with open(FILE_OUTPUT, "w") as f:
        for item in list_ads_url:
            f.write(str(item) + "\n")

    with open(FILE_OUTPUT_GOOGLE_ADS, "w") as f:
        for item in list_gg_ads:
            f.write(str(item) + "\n")
    
    with open(FILE_OUTPUT_GOOGLE_ADS_GCLID, "w") as f:
        for item in list_gg_ads_gclid:
            f.write(str(item) + "\n")
    
    with open(FILE_OUTPUT_SELECTED_VISIT_ADS, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["id_site","ads_url"])

        for i, url in enumerate(list_selected_url, start=1):
            writer.writerow([i, url])
    


if __name__ == "__main__":
    INPUT_DIR = f"captures"
    ROOT_DIR = Path(INPUT_DIR)

    FILE_OUTPUT = f"O_UniqueAdsURL.csv"
    FILE_OUTPUT_GOOGLE_ADS = f"O_google_ads_urls.csv"
    FILE_OUTPUT_GOOGLE_ADS_GCLID = f"O_google_ads_gclid_urls.csv"
    FILE_OUTPUT_SELECTED_VISIT_ADS = f"O_selected_adsURL.csv"

    collect_ads_by_country()

