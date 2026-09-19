from urllib.parse import urlparse, urljoin
import random
import time


EXCLUDED_KEYWORDS = [
    "login", "signin", "signup", "register", 
    "logout", "auth", "account",
    "ads", "advert", "tracking",
    "privacy", "policy", "terms",
    "cookie", "consent", "preferences",
    "help", "support", "contact", "about",
    "forum", "profile", "settings", "admin", "manage"
]


def is_excluded(url: str) -> bool:
    url_low = url.lower()
    return any(kw in url_low for kw in EXCLUDED_KEYWORDS)


def get_internal_links(driver, base_url):
    domain = urlparse(base_url).netloc
    elems = driver.find_elements("tag name", "a")
    links = set()

    for el in elems:
        href = el.get_attribute("href")
        if not href:
            continue


        href = urljoin(base_url, href)
        p = urlparse(href)


        if not p.scheme.startswith("http"):
            continue
        if p.netloc != domain:
            continue

        if is_excluded(href):
            continue

        links.add(href)

    return list(links)


def crawl_random_pages(driver, base_url, max_pages=10, delay=2):
    visited = set()

    driver.get(base_url)
    time.sleep(delay)
    visited.add(base_url)


    pool = get_internal_links(driver, base_url)

    if not pool:
        print("Not found any internal links")
        return visited

    print(f"Found {len(pool)} internal links.")


    random.shuffle(pool)

    for url in pool:
        if len(visited) >= max_pages:
            break

        if url in visited:
            continue

        print(f"[{len(visited)}/{max_pages}] → Visiting:", url)

        try:
            driver.get(url)
            time.sleep(delay)
            visited.add(url)
        except Exception as e:
            print("Error while open page:", url, e)

    print("\n DONE, got ", len(visited), "URL:")
    for u in visited:
        print(" -", u)

    return visited
