from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys


MARKER = ".adblocked-marker, .acceptablead-marker, .possiblead-marker, .adnetwork-marker"

import time
import json

import re
from bs4 import BeautifulSoup


def extract_by_label(soup, label_text):
    label_text = label_text.lower()

    for div in soup.find_all("div"):
        text = div.get_text(strip=True).lower()

        if text == label_text:
            parent = div.parent
            if not parent:
                continue

            # value thường nằm trong div kế tiếp
            siblings = parent.find_all("div", recursive=False)
            for sib in siblings:
                if sib is not div:
                    return sib.get_text(strip=True)

    return None

def extract_why_this_ad(html):
    soup = BeautifulSoup(html, "html.parser")

    reasons = []

    for h2 in soup.find_all("h2"):
        if h2.get_text(strip=True).lower() == "why this ad?":
            ul = h2.find_next("ul")
            if not ul:
                return []

            for li in ul.find_all("li"):
                reasons.append(li.get_text(strip=True))
            break

    return reasons


def extract_advertiser_location(html):
    soup = BeautifulSoup(html, "html.parser")

    advertiser_raw = extract_by_label(soup, "advertiser")
    location = extract_by_label(soup, "location")

    advertiser = None
    if advertiser_raw:
        advertiser = re.sub(r"paid for by", "", advertiser_raw, flags=re.I).strip()

    return {
        "advertiser": advertiser,
        "location": location
    }



def extract_see_more_ads(html):
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        if "see more ads" in a.get_text(strip=True).lower():
            return a["href"]

    return None



def extract_google_why_this_ad(html, url):
    soup = BeautifulSoup(html, "html.parser")

    advertiser_raw = extract_by_label(soup, "advertiser")
    location = extract_by_label(soup, "location")

    advertiser = None
    if advertiser_raw:
        advertiser = advertiser_raw.replace("Paid for by", "").strip()

    reasons = extract_why_this_ad(html)
    see_more = extract_see_more_ads(html)

    return {
        "adds_info_url": url,
        "advertiser": advertiser,
        "location": location,
        "why_this_ad": reasons,
        "see_more_ads_url": see_more
    }

# ========= END GET WHY THIS ADS ================================


def extract_ad_url_without_click(webdriver, ad_element):
    #print(ad_element.get_attribute("outerHTML"))
    #input("Press Enter to continue...")
    found_urls = []

    # Function to execute a script and return links
    def execute_script_and_get_links(script, *args):
        try:
            return webdriver.execute_script(script, *args)
        except Exception as e:
            #print(f"Error executing script: {e}")
            return []
    
    direct_links_script_org = """
        var links = [];
        var elements = arguments[0].querySelectorAll('a');
        elements.forEach(function(element) {
            var href = element.href;
            if (href) links.push(href);
        });
        return links;
    """

    direct_links_script = direct_links_script_org
    direct_links = execute_script_and_get_links(direct_links_script, ad_element)
    found_urls.extend(direct_links)

    #shadow_links = extract_urls_from_shadow_dom(webdriver, ad_element)
    #found_urls.extend(shadow_links)

    # Function to recursively find links within iframes
    def find_links_in_iframes(iframe_elements):
        for iframe in iframe_elements:
            try:
                webdriver.switch_to.frame(iframe)
                # Now that we're inside the iframe, look for links directly in this context
                links_in_iframe = execute_script_and_get_links(
                    """
                    var links = [];
                    document.querySelectorAll('a').forEach(function(element) {
                        var href = element.href;
                        if (href) links.push(href);
                    });
                    return links;
                """
                )
                found_urls.extend(links_in_iframe)

                # Look for nested iframes recursively
                nested_iframes = webdriver.find_elements(By.TAG_NAME, "iframe")
                find_links_in_iframes(nested_iframes)

                webdriver.switch_to.parent_frame()
            except Exception as e:
                # print(f"Error processing iframe: {e}")
                webdriver.switch_to.parent_frame()

    # Start by looking for iframes within the ad_element
    iframes_in_ad = ad_element.find_elements(By.TAG_NAME, "iframe")
    find_links_in_iframes(iframes_in_ad)

    # Ensure we're back at the top-level context after all processing
    webdriver.switch_to.default_content()
    #print(f"[INFO] Found {len(found_urls)} URLs in ad element.")

    return found_urls



def extract_urls_from_shadow_dom(webdriver, shadow_host):
    found_urls = []

    def execute_script(script, *args):
        try:
            return webdriver.execute_script(script, *args)
        except Exception:
            return []

    def traverse_shadow(host):
        # Lấy link trong shadow root hiện tại
        links = execute_script("""
            const host = arguments[0];
            if (!host.shadowRoot) return [];

            let urls = [];
            host.shadowRoot.querySelectorAll("a").forEach(a => {
                if (a.href)
                    urls.push(a.href);
            });

            return urls;
        """, host)

        found_urls.extend(links)

        # Tìm các shadow host con
        shadow_hosts = execute_script("""
            const host = arguments[0];
            if (!host.shadowRoot) return [];

            let result = [];

            host.shadowRoot.querySelectorAll("*").forEach(el => {
                if (el.shadowRoot)
                    result.push(el);
            });

            return result;
        """, host)

        for child in shadow_hosts:
            traverse_shadow(child)

        # Xử lý iframe trong shadow root
        iframes = execute_script("""
            const host = arguments[0];
            if (!host.shadowRoot) return [];

            return Array.from(
                host.shadowRoot.querySelectorAll("iframe")
            );
        """, host)

        for iframe in iframes:
            try:
                webdriver.switch_to.frame(iframe)

                links = execute_script("""
                    let urls = [];
                    document.querySelectorAll("a").forEach(a=>{
                        if(a.href)
                            urls.push(a.href);
                    });
                    return urls;
                """)

                found_urls.extend(links)

                webdriver.switch_to.parent_frame()

            except Exception:
                try:
                    webdriver.switch_to.parent_frame()
                except:
                    pass

    traverse_shadow(shadow_host)

    webdriver.switch_to.default_content()

    print(f"[INFO] Found {len(found_urls)} URLs in shadow DOM.")

    return found_urls



def run_get_e(driver, el):
    print("Get link ")

    result = click_and_capture_full_redirect_chain_e(driver, el)

    print("Opened new tab:", result["opened_new_tab"])

    print("\n[PRE-NAVIGATION CHAIN] (ads / trackers / SSP)")
    for item in result["pre_navigation_chain"]:
        print(f" -> {item['url']}  ({item['type']})")

    print("\n[NAVIGATION CHAIN] (Document redirects)")
    for url in result["navigation_chain"]:
        print(" ->", url)
                    
    print("\nFinal landing:", result["final_landing"])
    print("----")


    print("\n~DEVTOOL [PRE-NAVIGATION CHAIN]")
    for item in result["pre_navigation_chain"]:
        initiator = item.get("initiator", {})
        itype = initiator.get("type", "unknown")
        print(f" -> {item['url']}  [{item['type']}, initiator={itype}]")
                    
    print("----"*10)


def run_Click_and_getLog(driver, el):
    result = click_and_capture_full_redirect_chain(driver, el)

    print("Opened new tab:", result["opened_new_tab"])

    print("\n[PRE-NAVIGATION CHAIN]")
    for item in result["pre_navigation_chain"]:
        print(f" -> {item['url']}  ({item['type']})")

        init = item.get("initiator", {})
        if init:
            print(f"    initiator: {init.get('type')} | {init.get('url')}")

        for frame in item.get("stackTrace", []):
            print(
                f"      at {frame['function']} "
                f"({frame['url']}:{frame['line']}:{frame['column']})"
            )

    print("\n[NAVIGATION CHAIN]")
    for url in result["navigation_chain"]:
        print(" ->", url)

    print("\nFinal landing:", result["final_landing"])
    print("----")


def click_and_capture_full_redirect_chain(
    driver,
    element,
    timeout=10.0,
    pre_click_window=0.3
):
    """
    Capture full ad click chain:
    - PRE-navigation: JS / iframe / SSP / Google Ads / trackers
    - POST-navigation: Document redirect chain
    """

    original_window = driver.current_window_handle
    original_windows = set(driver.window_handles)

    pre_chain = []
    nav_chain = []
    seen_req = set()

    # clear old logs
    driver.get_log("performance")

    click_ts = time.time()

    # CLICK
    element.click()

    # ===========================
    # Phase A — PRE-navigation
    # ===========================
    while time.time() - click_ts < pre_click_window:
        logs = driver.get_log("performance")

        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") != "Network.requestWillBeSent":
                continue

            params = msg["params"]
            req = params["request"]
            req_id = params["requestId"]

            if req_id in seen_req:
                continue
            seen_req.add(req_id)

            initiator = params.get("initiator", {})
            stack = initiator.get("stack", {})
            call_frames = stack.get("callFrames", [])

            pre_chain.append({
                "url": req.get("url"),
                "type": params.get("type"),
                "initiator": {
                    "type": initiator.get("type"),
                    "url": initiator.get("url"),
                },
                "stackTrace": [
                    {
                        "function": f.get("functionName"),
                        "url": f.get("url"),
                        "line": f.get("lineNumber"),
                        "column": f.get("columnNumber"),
                    }
                    for f in call_frames[:8]   # giới hạn depth
                ]
            })

        time.sleep(0.005)

    # ===========================
    # Phase B — POST-navigation
    # ===========================
    start = time.time()
    opened_new_tab = False
    target_window = original_window

    while time.time() - start < timeout:
        current_windows = set(driver.window_handles)
        new_windows = current_windows - original_windows

        if new_windows:
            target_window = new_windows.pop()
            driver.switch_to.window(target_window)
            opened_new_tab = True

        logs = driver.get_log("performance")

        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method")

            if method == "Network.requestWillBeSent":
                params = msg["params"]
                if params.get("type") == "Document":
                    url = params["request"]["url"]
                    if url not in nav_chain:
                        nav_chain.append(url)

            if method == "Network.responseReceived":
                params = msg["params"]
                if params.get("type") == "Document":
                    resp = params["response"]
                    if resp.get("status") == 200:
                        final_url = resp.get("url")
                        if final_url not in nav_chain:
                            nav_chain.append(final_url)

                        if opened_new_tab:
                            driver.close()
                            driver.switch_to.window(original_window)

                        return {
                            "pre_navigation_chain": pre_chain,
                            "navigation_chain": nav_chain,
                            "final_landing": final_url,
                            "opened_new_tab": opened_new_tab
                        }

        time.sleep(0.01)

    # fallback
    if opened_new_tab:
        driver.close()
        driver.switch_to.window(original_window)

    return {
        "pre_navigation_chain": pre_chain,
        "navigation_chain": nav_chain,
        "final_landing": nav_chain[-1] if nav_chain else None,
        "opened_new_tab": opened_new_tab
    }


def click_and_capture_full_redirect_chain_e(
    driver,
    element,
    timeout=10.0,
    pre_click_window=0.3   # 300ms cho Google Ads click
):
    """
    Capture full ad click chain:
    - PRE-navigation: Google / SSP click (iframe, XHR, Image, Fetch)
    - POST-navigation: Document redirect chain to final landing
    """

    original_window = driver.current_window_handle
    original_windows = set(driver.window_handles)

    pre_chain = []     # Google / SSP / tracking
    nav_chain = []     # Document redirects
    seen_req = set()

    # clear logs
    driver.get_log("performance")

    # timestamp before click
    click_ts = time.time()

    # CLICK
    element.click()

    # ---------------------------
    # Phase A — PRE-navigation
    # ---------------------------
    while time.time() - click_ts < pre_click_window:
        logs = driver.get_log("performance")

        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") != "Network.requestWillBeSent":
                continue

            params = msg["params"]
            req = params["request"]
            req_id = params["requestId"]

            if req_id in seen_req:
                continue
            seen_req.add(req_id)

            # BẮT TẤT CẢ (KHÔNG filter Document)
            pre_chain.append({
                "url": req["url"],
                "type": params.get("type"),
                "initiator": params.get("initiator")
            })

        time.sleep(0.005)

    # ---------------------------
    # Phase B — POST-navigation
    # ---------------------------
    start = time.time()
    opened_new_tab = False
    target_window = original_window

    while time.time() - start < timeout:
        # detect new tab/window
        current_windows = set(driver.window_handles)
        new_windows = current_windows - original_windows

        if new_windows:
            target_window = new_windows.pop()
            driver.switch_to.window(target_window)
            opened_new_tab = True

        logs = driver.get_log("performance")

        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method")

            if method == "Network.requestWillBeSent":
                params = msg["params"]

                if params.get("type") == "Document":
                    url = params["request"]["url"]
                    if url not in nav_chain:
                        nav_chain.append(url)

            if method == "Network.responseReceived":
                params = msg["params"]

                if params.get("type") == "Document":
                    resp = params["response"]
                    if resp.get("status") == 200:
                        final_url = resp.get("url")
                        if final_url not in nav_chain:
                            nav_chain.append(final_url)

                        # DONE
                        if opened_new_tab:
                            driver.close()
                            driver.switch_to.window(original_window)

                        return {
                            "pre_navigation_chain": pre_chain,
                            "navigation_chain": nav_chain,
                            "final_landing": final_url,
                            "opened_new_tab": opened_new_tab
                        }

        time.sleep(0.01)

    # fallback
    if opened_new_tab:
        driver.close()
        driver.switch_to.window(original_window)

    return {
        "pre_navigation_chain": pre_chain,
        "navigation_chain": nav_chain,
        "final_landing": nav_chain[-1] if nav_chain else None,
        "opened_new_tab": opened_new_tab
    }


def click_and_capture_full_redirect_chain_SIMPLE(
    driver,
    element,
    timeout=10.0
):
    """
    Click element, capture full redirect chain until final landing page.
    Handles new tab/window automatically.
    
    Returns:
        {
          "chain": [url1, url2, ..., final_url],
          "final_url": str,
          "opened_new_tab": bool
        }
    """

    original_window = driver.current_window_handle
    original_windows = set(driver.window_handles)

    redirect_chain = []
    seen_request_ids = set()

    # clear old logs
    driver.get_log("performance")

    # click
    element.click()

    start = time.time()
    target_window = original_window
    opened_new_tab = False

    while time.time() - start < timeout:
        # detect new tab/window
        current_windows = set(driver.window_handles)
        new_windows = current_windows - original_windows

        if new_windows:
            target_window = new_windows.pop()
            driver.switch_to.window(target_window)
            opened_new_tab = True

        logs = driver.get_log("performance")

        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            method = msg.get("method")

            # Capture redirect
            if method == "Network.requestWillBeSent":
                params = msg["params"]
                request = params["request"]

                if params.get("type") == "Document":
                    req_id = params.get("requestId")

                    if req_id not in seen_request_ids:
                        seen_request_ids.add(req_id)
                        redirect_chain.append(request["url"])

            # Detect final landing (200 Document)
            if method == "Network.responseReceived":
                params = msg["params"]

                if params.get("type") == "Document":
                    response = params["response"]
                    status = response.get("status")

                    if status == 200:
                        final_url = response.get("url")

                        if final_url not in redirect_chain:
                            redirect_chain.append(final_url)

                        # DONE
                        result = {
                            "chain": redirect_chain,
                            "final_url": final_url,
                            "opened_new_tab": opened_new_tab
                        }

                        # cleanup
                        if opened_new_tab:
                            driver.close()
                            driver.switch_to.window(original_window)

                        return result

        time.sleep(0.01)

    # timeout fallback
    if opened_new_tab:
        driver.close()
        driver.switch_to.window(original_window)

    return {
        "chain": redirect_chain,
        "final_url": redirect_chain[-1] if redirect_chain else None,
        "opened_new_tab": opened_new_tab
    }



def extract_marked_metadata_all_frames(driver):
    results = []

    def scan_frame(depth=0, frame_path="root"):
        nonlocal results

        # --- 1) scan phần tử đánh dấu trong frame hiện tại ---
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, MARKER)
            for el in elems:
                try:
                    rect = driver.execute_script("""
                        const r = arguments[0].getBoundingClientRect();
                        return {x:r.left, y:r.top, width:r.width, height:r.height};
                    """, el)

                    html = driver.execute_script("return arguments[0].outerHTML;", el)

                    results.append({
                        "tag": el.tag_name,
                        "class": el.get_attribute("class"),
                        "rect": rect,
                        "html": html,
                        "frame_path": frame_path,
                        "page_url": driver.current_url
                    })

                except WebDriverException:
                    continue

        except WebDriverException:
            pass

        # --- 2) tìm và duyệt qua toàn bộ iframe con ---
        iframes = driver.find_elements(By.TAG_NAME, "iframe")

        for idx, iframe in enumerate(iframes):
            sub_path = f"{frame_path} -> iframe[{idx}]"

            try:
                driver.switch_to.frame(iframe)
            except Exception:
                # iframe cross-origin, không truy cập DOM được
                results.append({
                    "tag": "iframe",
                    "class": iframe.get_attribute("class"),
                    "rect": None,
                    "html": "<!-- CROSS ORIGIN IFRAME -->",
                    "frame_path": sub_path,
                    "page_url": driver.current_url
                })
                continue

            # đệ quy xuống iframe con
            scan_frame(depth + 1, sub_path)

            # trở lại frame cha
            driver.switch_to.parent_frame()

    # bắt đầu scan root frame
    scan_frame()
    return results



def classify_url(u: str):
    image_ext = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".ico", ".avif")
    video_ext = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v")
    audio_ext = (".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a")
    
    # Normalize
    low = u.lower().split("?")[0].split("#")[0]

    # Images
    if low.endswith(image_ext):
        return "image"

    # Media (video/audio)
    if low.endswith(video_ext) or low.endswith(audio_ext):
        return "image"

    # CSS background-image inline URL
    if any(x in u.lower() for x in ["data:image/", "base64,i"]):
        return "image"

    # Typical links or JS/CSS/API
    return "link"

def split_urls(urls):
    images = []
    links = []
    #media = []

    for u in urls:
        t = classify_url(u)
        if t == "image":
            images.append(u)
        # elif t == "media":
        #     media.append(u)
        else:
            links.append(u)

    return {
        "images": images,
        #"media": media,
        "links": links
    }


def extract_urls_from_html(html):
    import re
    if not html:
        return []

    url_pattern = re.compile(
        r"""(?i)
        (?:
            src\s*=\s*["']([^"']+)["'] |
            href\s*=\s*["']([^"']+)["'] |
            data-src\s*=\s*["']([^"']+)["'] |
            data-url\s*=\s*["']([^"']+)["'] |
            url\(\s*["']?([^"')]+)["']?\s*\) |
            (https?://[^\s"'<>]+)
        )
        """, re.VERBOSE
    )

    results = set()

    for match in url_pattern.findall(html):
        for u in match:
            if u:
                results.add(u)

    return list(results)


#Keep
def extract_marked_metadata(driver):
    script_new = """
    function getXPath(el) {
      if (el.id) return '//*[@id="' + el.id + '"]';
      var parts = [];
      while (el && el.nodeType === 1) {
        var idx = 1;
        var sib = el.previousSibling;
        while (sib) {
          if (sib.nodeType === 1 && sib.tagName === el.tagName) idx++;
          sib = sib.previousSibling;
        }
        parts.unshift(el.tagName.toLowerCase() + '[' + idx + ']');
        el = el.parentNode;
      }
      return '/' + parts.join('/');
    }
    
    function extractMarkedElementsKeepChild() {
      var markers = [
        'adblocked-marker',
        'acceptablead-marker',
        'possiblead-marker',
        'adnetwork-marker'
      ];
      var selector = '';
      for (var i = 0; i < markers.length; i++) {
        if (i > 0) selector += ',';
        selector += '.' + markers[i];
      }
      var elems = Array.prototype.slice.call(document.querySelectorAll(selector));
      var withXPath = [];
      for (var i = 0; i < elems.length; i++) {
        withXPath.push({
          el: elems[i],
          xpath: getXPath(elems[i])
        });
      }
      // sort deepest first
      withXPath.sort(function(a, b) {
        return b.xpath.length - a.xpath.length;
      });

      var kept = [];

      for (var i = 0; i < withXPath.length; i++) {
        var item = withXPath[i];
        var isParent = false;
        
        for (var j = 0; j < kept.length; j++) {
          if (kept[j].xpath.indexOf(item.xpath + '/') === 0) {
            isParent = true;
            break;
          }
        }

        if (!isParent) {
          kept.push(item);
        }
      }
      
      var result = [];
      for (var i = 0; i < kept.length; i++) {
        var el = kept[i].el;
        result.push({
          tag: el.tagName.toLowerCase(),
          classes: el.className,
          xpath: kept[i].xpath,
          rect: el.getBoundingClientRect().toJSON(),
          html: el.outerHTML,
          link: el.src || el.href || ""
        });
      }
      return result;
    }
    return extractMarkedElementsKeepChild();
    """

    elements = driver.execute_script(script_new)
    page_url = driver.current_url
    for el in elements:
        el["page_url"] = page_url
    print(f"[INFO] Found {len(elements)} marked elements on {page_url}")
    return elements



#keep
def capture_marked_elements_lite(driver, outdir):
    import os
    import time

    os.makedirs(outdir, exist_ok=True)
    metadata = extract_marked_metadata(driver)

    for i, ad in enumerate(metadata):
        fname = ""
        try:
            rect = ad["rect"]
            driver.execute_script("window.scrollTo(arguments[0], arguments[1]);", rect["x"], rect["y"] - 100)
            time.sleep(0.5)

            
            el = driver.execute_script(f"""return document.querySelectorAll('.adblocked-marker, .acceptablead-marker, .possiblead-marker, .adnetwork-marker')[arguments[0]];""", i)
            

            if el:
                urls = extract_ad_url_without_click(driver, el)
                urls = set(urls)
                if urls:
                    filename = os.path.join(outdir, "Ads_URL.txt")
                    existing_items0 = set()
                    with open(filename, 'a+', encoding='utf-8') as file:
                        file.seek(0)  # Move the cursor to the beginning of the file
                        for line in file:
                            line = line.strip()
                            if line:
                                existing_items0.add(line)

                        for item in urls:
                            if item not in existing_items0:
                                file.write(f"{item}\n") # Use an f-string to append a newline
                #print("-----------------------------------------------")

                    
        except Exception as e:
            pass

from urllib.parse import urlparse, parse_qs


from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import time

def get_hover_link(driver, element):
    # 1) Hover
    try:
        ActionChains(driver).move_to_element(element).perform()
        time.sleep(0.3)
    except:
        return ""

    # 2) JS để đọc link khi hover
    js_extract = """
        const el = arguments[0];

        // direct attributes
        const attrs = ["href", "src", "data-href", "data-url", "data-link"];
        for (let a of attrs) {
            const v = el.getAttribute(a);
            if (v) return v;
        }

        // closest <a>
        const a = el.closest("a");
        if (a && a.href) return a.href;

        // inline JS URL
        if (typeof el.onclick === "function") {
            const code = el.onclick.toString();
            const m = code.match(/https?:\\/\\/[^'"\\s]+/);
            if (m) return m[0];
        }

        // url trong chính html
        const html = el.outerHTML;
        const mm = html.match(/https?:\\/\\/[^'"\\s]+/);
        if (mm) return mm[0];

        return "";
    """
    try:
        link = driver.execute_script(js_extract, element)
        if link:
            return link
    except:
        pass

    # 3) Tìm link xuất hiện khi hover (thường popup tooltip)
    try:
        hover_a = driver.find_element(By.CSS_SELECTOR, "a:hover")
        return hover_a.get_attribute("href")
    except:
        pass

    return ""



import threading


def get_copy_link_address(driver, element):
    """
    Click element (nhưng chặn redirect), bắt URL outbound đầu tiên.
    Trả lại đúng URL mà Chrome sẽ copy khi bấm 'Copy link address'.
    """

    driver.execute_cdp_cmd("Network.enable", {})

    result = {"url": None}

    def intercept_requests():
        def callback(params):
            if not result["url"]:
                req = params.get("request", {})
                # bắt link đầu tiên do element click tạo ra
                result["url"] = req.get("url")

            # chặn redirect nên tab không rời trang
            driver.execute_cdp_cmd("Network.cancelRequest", {
                "requestId": params["requestId"]
            })

        driver.add_cdp_listener("Network.requestWillBeSent", callback)

    threading.Thread(target=intercept_requests, daemon=True).start()

    # click thật vào element nhưng tab không rời trang
    ActionChains(driver).move_to_element(element).click().perform()

    # đợi request
    timeout = time.time() + 1.5
    while time.time() < timeout:
        if result["url"]:
            break
        time.sleep(0.05)

    return result["url"]



def BingYahoo_capture_marked_elements(driver, screenshot=False):   
    metadata = BingYahoo_extract_marked_metadata(driver)
    hrefs = set()
    for i, ad in enumerate(metadata):
        fname = ""
        try:
            rect = ad["rect"]
            driver.execute_script("window.scrollTo(arguments[0], arguments[1]);", rect["x"], rect["y"] - 100)
            time.sleep(0.5)
            
            el = driver.execute_script(r"""
                                            function collectElements(root, selector, result) {
                                                result = result || [];
                                                if (!root || !root.querySelectorAll)
                                                    return result;

                                                var found = root.querySelectorAll(selector);

                                                for (var i = 0; i < found.length; i++)
                                                    result.push(found[i]);

                                                var all = root.querySelectorAll("*");

                                                for (var i = 0; i < all.length; i++) {
                                                    if (all[i].shadowRoot) {
                                                        collectElements(all[i].shadowRoot, selector, result);
                                                    }
                                                }

                                                return result;
                                            }
                                           
                                            var markers = [
                                                "adblocked-marker",
                                                "acceptablead-marker",
                                                "possiblead-marker",
                                                "adnetwork-marker",
                                                "adblocked-acceptablead-marker",
                                                "ad-special-marker",
                                                "ad-attr-heuristic-marker",
                                                "ad-metadata-marker"
                                            ];

                                            var selector = markers.map(function(c){
                                                return "." + c;
                                            }).join(",");

                                            var elems = collectElements(document, selector);

                                            return elems[arguments[0]];
                                           """, i)
            
            if el:
                # if screenshot:
                #     # Save screenshot
                #     class_name = ad["classes"].split()[0] if ad["classes"] else "marked"
                #     fname = os.path.join(outdir, f"{class_name}_{i}.png")
                #     safe_element_screenshot(driver, el, fname)
                #     #png = el.screenshot_as_png
                #     #with open(fname, "wb") as f:
                #     #    f.write(png)
                #     print(f"[OK] Captured: {fname}")

                urls = BingYahoo_extract_ad_url_without_click(driver, el)
                urls = set(urls)
                if urls:
                    for u in urls:
                        hrefs.add(u)
                    # filename = os.path.join(outdir, "Ads_URL.txt")
                    # existing_items0 = set()
                    # with open(filename, 'a+', encoding='utf-8') as file:
                    #     file.seek(0)  # Move the cursor to the beginning of the file
                    #     for line in file:
                    #         line = line.strip()
                    #         if line:
                    #             existing_items0.add(line)

                    #     for item in urls:
                    #         if item not in existing_items0:
                    #             if screenshot:
                    #                 file.write(f"{item},{fname}\n") # Use an f-string to append a newline
                    #             else:
                    #                 file.write(f"{item}\n") # Use an f-string to append a newline
                #print("-----------------------------------------------")
                    
        except Exception as e:
            pass
    return hrefs



def BingYahoo_extract_marked_metadata(driver):
    """
    Trích xuất metadata của tất cả phần tử được extension đánh dấu.
    Trả về danh sách dict gồm:
        tag, class, rect, html, link, page_url
    """


    script_test_upd = r"""
function getDomPath(el) {
    var parts = [];

    while (el) {

        // Document
        if (el.nodeType === Node.DOCUMENT_NODE) {
            break;
        }

        // ShadowRoot
        if (el.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
            parts.unshift("#shadow-root");
            el = el.host;
            continue;
        }

        // Skip non-element nodes
        if (el.nodeType !== Node.ELEMENT_NODE) {
            el = el.parentNode;
            continue;
        }

        if (el.id) {
            parts.unshift('//*[@id="' + el.id + '"]');
            break;
        }

        var idx = 1;
        var sib = el.previousElementSibling;

        while (sib) {
            if (sib.tagName === el.tagName) {
                idx++;
            }
            sib = sib.previousElementSibling;
        }

        parts.unshift(
            el.tagName.toLowerCase() + "[" + idx + "]"
        );

        el = el.parentNode;
    }

    return "/" + parts.join("/");
}

function collectElements(root, selector, result) {
    result = result || [];

    if (!root || !root.querySelectorAll) {
        return result;
    }

    var found = root.querySelectorAll(selector);
    for (var i = 0; i < found.length; i++) {
        result.push(found[i]);
    }

    var all = root.querySelectorAll("*");

    for (var i = 0; i < all.length; i++) {
        if (all[i].shadowRoot) {
            collectElements(all[i].shadowRoot, selector, result);
        }
    }

    return result;
}

function isAncestor(parent, child) {
    var node = child;

    while (node) {

        if (node === parent) {
            return true;
        }

        if (node.parentNode) {
            node = node.parentNode;
        } else if (node.host) {
            // ShadowRoot -> host
            node = node.host;
        } else {
            node = null;
        }
    }

    return false;
}

function extractMarkedElementsKeepChild() {

    var markers = [
        "adblocked-marker",
        "acceptablead-marker",
        "possiblead-marker",
        "adnetwork-marker",
        "adblocked-acceptablead-marker",
        "ad-special-marker",
        "ad-attr-heuristic-marker",
        "ad-metadata-marker"
    ];

    var selector = "";

    for (var i = 0; i < markers.length; i++) {
        if (i > 0) selector += ",";
        selector += "." + markers[i];
    }

    // Search in document + all open shadow roots
    var elems = collectElements(document, selector);

    var withPath = [];

    for (var i = 0; i < elems.length; i++) {
        withPath.push({
            el: elems[i],
            path: getDomPath(elems[i])
        });
    }

    // deepest first
    withPath.sort(function(a, b) {
        return b.path.length - a.path.length;
    });

    var kept = [];

    for (var i = 0; i < withPath.length; i++) {

        var item = withPath[i];
        var isParent = false;

        for (var j = 0; j < kept.length; j++) {
            if (isAncestor(item.el, kept[j].el)) {
                isParent = true;
                break;
            }
        }

        if (!isParent) {
            kept.push(item);
        }
    }

    var result = [];

    for (var i = 0; i < kept.length; i++) {

        var el = kept[i].el;

        if (!el || !el.tagName) {
            continue;
        }

        result.push({
            tag: el.tagName.toLowerCase(),
            classes: el.className,
            xpath: kept[i].path,
            rect: el.getBoundingClientRect().toJSON(),
            html: el.outerHTML,
            link: el.src || el.href || ""
        });
    }

    return result;
}

return extractMarkedElementsKeepChild();
"""
    
    elements = driver.execute_script(script_test_upd)
    page_url = driver.current_url
    for el in elements:
        el["page_url"] = page_url
    print(f"[INFO] Found {len(elements)} marked elements on {page_url}")
    return elements


def BingYahoo_extract_ad_url_without_click(webdriver, ad_element):
    found_urls = []

    # Function to execute a script and return links
    def execute_script_and_get_links(script, *args):
        try:
            return webdriver.execute_script(script, *args)
        except Exception as e:
            #print(f"Error executing script: {e}")
            return []

    # Extract links directly within the ad_element
    direct_links_script_new = r"""
        var links = [];
        var root = arguments[0];

        function add(url) {
            if (!url) return;
            url = String(url).trim();
            if (url && links.indexOf(url) === -1) {
                links.push(url);
            }
        }

        function parseDataAdUrls(value) {
            if (!value) return;
            try {
                var obj = JSON.parse(value);
                if (Array.isArray(obj)) {
                    obj.forEach(function(item){
                        if (!item) return;
                        if (typeof item === "string") {
                            add(item);
                        }
                        if (item.url) {
                            add(item.url);
                        }
                        if (item.href) {
                            add(item.href);
                        }
                    });
                } else if (typeof obj === "object") {
                    if (obj.url)
                        add(obj.url);
                    if (obj.href)
                        add(obj.href);
                }
            } catch(e) {
                // data-ad-urls không phải JSON
                add(value);
            }
        }

        //--------------------------------------------------
        // 1. Chính element là <a>
        //--------------------------------------------------
        if (
            root.tagName &&
            root.tagName.toLowerCase() === "a"
        ) {
            add(root.href);
        }


        //--------------------------------------------------
        // 2. Tất cả <a> bên trong
        //--------------------------------------------------

        root.querySelectorAll("a").forEach(function(a){
            add(a.href);
        });


        //--------------------------------------------------
        // 3. data-ad-urls trên chính element
        //--------------------------------------------------

        parseDataAdUrls(
            root.getAttribute("data-ad-urls")
        );


        //--------------------------------------------------
        // 4. data-ad-urls trên tất cả descendant
        //--------------------------------------------------

        root.querySelectorAll("[data-ad-urls]").forEach(function(el){

            parseDataAdUrls(
                el.getAttribute("data-ad-urls")
            );

        });


        //--------------------------------------------------
        // 5. Một số ad network dùng data-href
        //--------------------------------------------------

        if (root.hasAttribute("data-href"))
            add(root.getAttribute("data-href"));

        root.querySelectorAll("[data-href]").forEach(function(el){
            add(el.getAttribute("data-href"));
        });


        //--------------------------------------------------
        // 6. Một số ad network dùng data-url
        //--------------------------------------------------

        if (root.hasAttribute("data-url"))
            add(root.getAttribute("data-url"));

        root.querySelectorAll("[data-url]").forEach(function(el){
            add(el.getAttribute("data-url"));
        });


        return links;
        """
    
    direct_links = execute_script_and_get_links(direct_links_script_new, ad_element)
    found_urls.extend(direct_links)

    #shadow_links = extract_urls_from_shadow_dom(webdriver, ad_element)
    #found_urls.extend(shadow_links)

    # Function to recursively find links within iframes
    def find_links_in_iframes(iframe_elements):
        for iframe in iframe_elements:
            try:
                webdriver.switch_to.frame(iframe)
                # Now that we're inside the iframe, look for links directly in this context
                links_in_iframe = execute_script_and_get_links(
                    """
                    var links = [];
                    document.querySelectorAll('a').forEach(function(element) {
                        var href = element.href;
                        if (href) links.push(href);
                    });
                    return links;
                """
                )
                found_urls.extend(links_in_iframe)

                # Look for nested iframes recursively
                nested_iframes = webdriver.find_elements(By.TAG_NAME, "iframe")
                find_links_in_iframes(nested_iframes)

                webdriver.switch_to.parent_frame()
            except Exception as e:
                # print(f"Error processing iframe: {e}")
                webdriver.switch_to.parent_frame()

    # Start by looking for iframes within the ad_element
    iframes_in_ad = ad_element.find_elements(By.TAG_NAME, "iframe")
    find_links_in_iframes(iframes_in_ad)

    # Ensure we're back at the top-level context after all processing
    webdriver.switch_to.default_content()
    #print(f"[INFO] Found {len(found_urls)} URLs in ad element.")

    return found_urls





def GoogleAds_capture_marked_elements(driver, screenshot=False):
    metadata = GoogleAds_extract_marked_metadata(driver)
    hrefs = set()
    for i, ad in enumerate(metadata):
        fname = ""
        try:
            rect = ad["rect"]
            driver.execute_script("window.scrollTo(arguments[0], arguments[1]);", rect["x"], rect["y"] - 100)
            time.sleep(0.5)

            
            el = driver.execute_script(f"""return document.querySelectorAll('.adblocked-marker, .acceptablead-marker, .possiblead-marker, .adnetwork-marker')[arguments[0]];""", i)
            
            
            if el:
                # if screenshot:
                #     # Save screenshot
                #     class_name = ad["classes"].split()[0] if ad["classes"] else "marked"
                #     fname = os.path.join(outdir, f"{class_name}_{i}.png")
                #     safe_element_screenshot(driver, el, fname)
                #     #png = el.screenshot_as_png
                #     #with open(fname, "wb") as f:
                #     #    f.write(png)
                #     print(f"[OK] Captured: {fname}")

                urls = GoogleAds_extract_ad_url_without_click(driver, el)
                urls = set(urls)
                if urls:
                    for u in urls:
                        hrefs.add(u)
                #print("-----------------------------------------------")
                    
        except Exception as e:
            pass
    return hrefs


def GoogleAds_extract_marked_metadata(driver):
    """
    Trích xuất metadata của tất cả phần tử được extension đánh dấu.
    Trả về danh sách dict gồm:
        tag, class, rect, html, link, page_url
    """


    script_new_org = """
    function getXPath(el) {
      if (el.id) return '//*[@id="' + el.id + '"]';
      var parts = [];
      while (el && el.nodeType === 1) {
        var idx = 1;
        var sib = el.previousSibling;
        while (sib) {
          if (sib.nodeType === 1 && sib.tagName === el.tagName) idx++;
          sib = sib.previousSibling;
        }
        parts.unshift(el.tagName.toLowerCase() + '[' + idx + ']');
        el = el.parentNode;
      }
      return '/' + parts.join('/');
    }
    
    function extractMarkedElementsKeepChild() {
      var markers = [
        'adblocked-marker',
        'acceptablead-marker',
        'possiblead-marker',
        'adnetwork-marker'
      ];
      var selector = '';
      for (var i = 0; i < markers.length; i++) {
        if (i > 0) selector += ',';
        selector += '.' + markers[i];
      }
      var elems = Array.prototype.slice.call(document.querySelectorAll(selector));
      var withXPath = [];
      for (var i = 0; i < elems.length; i++) {
        withXPath.push({
          el: elems[i],
          xpath: getXPath(elems[i])
        });
      }
      // sort deepest first
      withXPath.sort(function(a, b) {
        return b.xpath.length - a.xpath.length;
      });

      var kept = [];

      for (var i = 0; i < withXPath.length; i++) {
        var item = withXPath[i];
        var isParent = false;
        
        for (var j = 0; j < kept.length; j++) {
          if (kept[j].xpath.indexOf(item.xpath + '/') === 0) {
            isParent = true;
            break;
          }
        }

        if (!isParent) {
          kept.push(item);
        }
      }
      
      var result = [];
      for (var i = 0; i < kept.length; i++) {
        var el = kept[i].el;
        result.push({
          tag: el.tagName.toLowerCase(),
          classes: el.className,
          xpath: kept[i].xpath,
          rect: el.getBoundingClientRect().toJSON(),
          html: el.outerHTML,
          link: el.src || el.href || ""
        });
      }
      return result;
    }
    return extractMarkedElementsKeepChild();
    """

    elements = driver.execute_script(script_new_org)
    page_url = driver.current_url
    for el in elements:
        el["page_url"] = page_url
    print(f"[INFO] Found {len(elements)} marked elements on {page_url}")
    return elements


def GoogleAds_extract_ad_url_without_click(webdriver, ad_element):
    #print(ad_element.get_attribute("outerHTML"))
    #input("Press Enter to continue...")
    found_urls = []

    # Function to execute a script and return links
    def execute_script_and_get_links(script, *args):
        try:
            return webdriver.execute_script(script, *args)
        except Exception as e:
            #print(f"Error executing script: {e}")
            return []

    # Extract links directly within the ad_element
    direct_links_script_org = """
        var links = [];
        var elements = arguments[0].querySelectorAll('a');
        elements.forEach(function(element) {
            var href = element.href;
            if (href) links.push(href);
        });
        return links;
    """
    direct_links = execute_script_and_get_links(direct_links_script_org, ad_element)
    found_urls.extend(direct_links)

    #shadow_links = extract_urls_from_shadow_dom(webdriver, ad_element)
    #found_urls.extend(shadow_links)

    # Function to recursively find links within iframes
    def find_links_in_iframes(iframe_elements):
        for iframe in iframe_elements:
            try:
                webdriver.switch_to.frame(iframe)
                # Now that we're inside the iframe, look for links directly in this context
                links_in_iframe = execute_script_and_get_links(
                    """
                    var links = [];
                    document.querySelectorAll('a').forEach(function(element) {
                        var href = element.href;
                        if (href) links.push(href);
                    });
                    return links;
                """
                )
                found_urls.extend(links_in_iframe)

                # Look for nested iframes recursively
                nested_iframes = webdriver.find_elements(By.TAG_NAME, "iframe")
                find_links_in_iframes(nested_iframes)

                webdriver.switch_to.parent_frame()
            except Exception as e:
                # print(f"Error processing iframe: {e}")
                webdriver.switch_to.parent_frame()

    # Start by looking for iframes within the ad_element
    iframes_in_ad = ad_element.find_elements(By.TAG_NAME, "iframe")
    find_links_in_iframes(iframes_in_ad)

    # Ensure we're back at the top-level context after all processing
    webdriver.switch_to.default_content()
    #print(f"[INFO] Found {len(found_urls)} URLs in ad element.")

    return found_urls