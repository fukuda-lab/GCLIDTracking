import psycopg2, json
from contextlib import contextmanager
from psycopg2.extras import Json, execute_batch
import base64
from urllib.parse import urlparse
import psycopg2.extras
import time
import re
from libs.config import DB_CONFIG, DB_DEFAULT

def safe_json_stream(s):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None

    objs = []
    decoder = json.JSONDecoder()
    while s:
        try:
            obj, idx = decoder.raw_decode(s)
            objs.append(obj)
            s = s[idx:].lstrip()
        except json.JSONDecodeError:
            break
    return objs if objs else None


def debug_rows0(rows):
    for i, row in enumerate(rows):
        for j, col in enumerate(row):
            if isinstance(col, dict):
                raise TypeError(f"DICT FOUND at row {i}, col {j}")
            if isinstance(col, list):
                raise TypeError(f"LIST FOUND at row {i}, col {j}")

def debug_rows(rows):
    errors = []
    for i, row in enumerate(rows):
        for j, col in enumerate(row):
            if isinstance(col, dict):
                errors.append((i, j, "dict", col))
            elif isinstance(col, list):
                errors.append((i, j, "list", col))
    return errors

def strip_nul(v):
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.replace(b'\x00', b'').decode('utf-8', errors='ignore')
    if isinstance(v, str):
        return v.replace('\x00', '')
    if isinstance(v, dict):
        return {k: strip_nul(val) for k, val in v.items()}
    if isinstance(v, list):
        return [strip_nul(x) for x in v]
    return v

def sanitize_text_OLD_(s):
    if s is None:
        return None
    return s.replace("\x00", "")

def sanitize_text(s):
    if s is None:
        return None
    if isinstance(s, bytes):
        s = s.decode("utf-8", errors="ignore")
    return str(s).replace("\x00", "")


def update_cfg(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD):
    if DB_HOST == "":
        DB_HOST = "localhost"
    
    if DB_PORT == "":
        DB_PORT = 5432
    else:
        try:
            DB_PORT = int(DB_PORT)
        except:
            raise ValueError("Port must be a number")
    
    if DB_NAME == "" or DB_USER == "" or DB_PASSWORD == "":
        print("Error!!")
        raise ValueError("Name, User, Password can not blank!")
   
    with open("libs/config.py", "r", encoding="utf-8") as f:
        content = f.read()

    def replace(key, value, is_string=True):
        if is_string:
            pattern = rf'{key}\s*=\s*".*?"'
            replacement = f'{key} = "{value}"'
        else:
            pattern = rf'{key}\s*=\s*\d+'
            replacement = f'{key} = {value}'
        return re.sub(pattern, replacement, content)

    content_updated = content
    content_updated = re.sub(r'DB_HOST\s*=\s*".*?"', f'DB_HOST = "{DB_HOST}"', content_updated)
    content_updated = re.sub(r'DB_NAME\s*=\s*".*?"', f'DB_NAME = "{DB_NAME}"', content_updated)
    content_updated = re.sub(r'DB_USER\s*=\s*".*?"', f'DB_USER = "{DB_USER}"', content_updated)
    content_updated = re.sub(r'DB_PASSWORD\s*=\s*".*?"', f'DB_PASSWORD = "{DB_PASSWORD}"', content_updated)
    content_updated = re.sub(r'DB_PORT\s*=\s*.*',f'DB_PORT = {DB_PORT}',content_updated)
    

    with open("libs/config.py", "w", encoding="utf-8") as f:
        f.write(content_updated)

    print("Config updated successfully!")


@contextmanager
def get_db_conn(default = False):
    if default:
        conn = psycopg2.connect(**DB_DEFAULT)
    else:
        conn = psycopg2.connect(**DB_CONFIG)
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def insert_site_GeneralAds(conn, domain_url, id_csv, ip, country, run_no, platform, status, error=None, reached_url=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sites (
                domain_url, crawl_date, crawl_time, id_csv, ip, country, run_no, platform, crawl_status, error_message, reached_url
            )
            VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_site
        """, (domain_url, id_csv, ip, country, run_no, platform, status, error, reached_url))
        return cur.fetchone()[0]


def insert_site_visitedAds(conn, domain_url, id_csv, ip, country, run_no, choice, status, error=None, reached_url=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sites (
                domain_url, crawl_date, crawl_time, id_csv, ip, country, run_no, choice, crawl_status, error_message, reached_url
            )
            VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_site
        """, (domain_url, id_csv, ip, country, run_no, choice, status, error, reached_url))
        return cur.fetchone()[0]

def insert_site(conn, domain_url, profile, country, run_no, ip, status, error=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sites (
                domain_url, crawl_date, crawl_time,
                profile_name, country, run_no, ip_address, crawl_status, error_message
            )
            VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s)
            RETURNING id_site
        """, (domain_url, profile, country, run_no, ip, status, error))
        return cur.fetchone()[0]
    
def to_text(val):
    if val is None:
        return None
    try:
        s = str(val)
        return s.replace("\x00", "")
    except Exception:
        return None


def upsert_page(conn, id_site, page_url, title=None, status=None, ctype=None):

    path = urlparse(page_url).path
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pages (
                id_site, page_url, page_path,
                page_title, http_status, content_type
            )
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id_site, page_url)
            DO UPDATE SET last_seen_at = CURRENT_TIMESTAMP
            RETURNING page_id
        """, (id_site, page_url, path, title, status, ctype))
        return cur.fetchone()[0]

def insert_run(conn, id_site, page_id, page_url):
    domain = urlparse(page_url).netloc
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO runs (id_site, page_id, page_url, domain_url, status)
            VALUES (%s,%s,%s,%s,'partial')
            RETURNING run_id
        """, (id_site, page_id, page_url, domain))
        return cur.fetchone()[0]
    
def save_local_storage_pg(conn, id_site, id_csv, country, run_no, choice, this_domain, local_storage, current_url, origin, after=False):
    """
    Save all local storage entries into PostgreSQL
    :param driver: selenium driver
    :param id_site: sites.id_site
    :param id_csv: sites.id_csv
    :param country: sites.country
    :param run_no: sites.run_no
    :param this_domain: domain that is being crawled
    :param after: True if crawl after accept/reject consent
    """

    cursor = conn.cursor()

    sql = """
        INSERT INTO local_storage (
            id_site,
            id_csv,
            country,
            run_no,
            choice,
            lstorage_key,
            lstorage_value,
            is_after,
            current_domain,
            current_url,
            origin
        )
        VALUES (
            %(id_site)s,
            %(id_csv)s,
            %(country)s,
            %(run_no)s,
            %(choice)s,
            %(lstorage_key)s,
            %(lstorage_value)s,
            %(is_after)s,
            %(current_domain)s,
            %(current_url)s,
            %(origin)s
        )
    """

    rows = []
    for k, v in local_storage.items():
        rows.append({
            "id_site": id_site,
            "id_csv": id_csv,
            "country": country,
            "run_no": run_no,
            "choice": choice,
            "lstorage_key": to_text(str(k)),
            "lstorage_value": to_text(str(v)),
            "is_after": bool(after),
            "current_domain": this_domain,
            "current_url": current_url,
            "origin": origin
        })
    
    if not rows:
        return
    

    try:
        execute_batch(cursor, sql, rows, page_size=200)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving local storage: {e}")

def save_session_storage_pg(conn, id_site, id_csv, country, run_no, choice, this_domain, session_storage, current_url, origin, after=False):
    """
    Save all session storage entries into PostgreSQL
    :param driver: selenium driver
    :param id_site: sites.id_site
    :param id_csv: sites.id_csv
    :param country: sites.country
    :param run_no: sites.run_no
    :param this_domain: domain that is being crawled
    :param after: True if crawl after accept/reject consent
    """

    cursor = conn.cursor()

    sql = """
        INSERT INTO session_storage (
            id_site,
            id_csv,
            country,
            run_no,
            choice,
            sstorage_key,
            sstorage_value,
            is_after,
            current_domain,
            current_url,
            origin
        )
        VALUES (
            %(id_site)s,
            %(id_csv)s,
            %(country)s,
            %(run_no)s,
            %(choice)s,
            %(sstorage_key)s,
            %(sstorage_value)s,
            %(is_after)s,
            %(current_domain)s,
            %(current_url)s,
            %(origin)s
        )
    """

    rows = []
    for k, v in session_storage.items():
        rows.append({
            "id_site": id_site,
            "id_csv": id_csv,
            "country": country,
            "run_no": run_no,
            "choice": choice,
            "sstorage_key": to_text(str(k)),
            "sstorage_value": to_text(str(v)),
            "is_after": bool(after),
            "current_domain": this_domain,
            "current_url": current_url,
            "origin": origin
        })
    
    if not rows:
        return
    

    try:
        execute_batch(cursor, sql, rows, page_size=200)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving session storage: {e}")

def save_cookies_pg(conn, id_site, id_csv, country, run_no, choice, this_domain, cookies, current_url, origin, after=False):
    cursor = conn.cursor()

    sql = """
        INSERT INTO cookies (
            id_site,
            id_csv,
            country,
            run_no,
            choice,
            name,
            value,
            domain,
            path,
            expires,
            expires_convert,
            is_http_only,
            is_secure,
            session,
            same_site,
            priority,
            size,
            source_port,
            source_scheme,
            partition_key,
            is_after,
            current_domain,
            current_url,
            origin
        )
        VALUES (
            %(id_site)s,
            %(id_csv)s,
            %(country)s,
            %(run_no)s,
            %(choice)s,
            %(name)s,
            %(value)s,
            %(domain)s,
            %(path)s,
            %(expires)s,
            %(expires_convert)s,
            %(is_http_only)s,
            %(is_secure)s,
            %(session)s,
            %(same_site)s,
            %(priority)s,
            %(size)s,
            %(source_port)s,
            %(source_scheme)s,
            %(partition_key)s,
            %(is_after)s,
            %(current_domain)s,
            %(current_url)s,
            %(origin)s
        )
    """

    rows = []
    for cookie in cookies.get("cookies", []):
        expires = cookie.get("expires")
        expires_convert = None
        if expires and expires != -1:
            expires_convert = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(expires)
            )
        partition_key = cookie.get("partitionKey")
        rows.append({
            "id_site": id_site,
            "id_csv": id_csv,
            "country": country,
            "run_no": run_no,
            "choice": choice,
            "name": cookie.get("name"),
            "value": cookie.get("value"),
            "domain": cookie.get("domain"),
            "path": cookie.get("path"),
            "expires": expires,
            "expires_convert": expires_convert,
            "is_http_only": cookie.get("httpOnly"),
            "is_secure": cookie.get("secure"),
            "session": cookie.get("session"),
            "same_site": cookie.get("sameSite"),
            "priority": cookie.get("priority"),
            "size": cookie.get("size"),
            "source_port": cookie.get("sourcePort"),
            "source_scheme": cookie.get("sourceScheme"),
            "partition_key": str(partition_key),
            "is_after": bool(after),
            "current_domain": this_domain,
            "current_url": current_url,
            "origin": origin
        })
    
    if not rows:
        return
    

    try:
        execute_batch(cursor, sql, rows, page_size=200)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving cookies: {e}")
    
def safe_json(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return Json(v)
    return Json(strip_nul(v))

#def safe_json(v):
#    return json.dumps(v) if v is not None else None

def save_full_network_data_AdsLanding(conn, driver, id_site, id_csv, country, run_no, choice, page_url, events, after=None):
    req_rows = []
    res_rows = []
    req_extra = []
    res_extra = []
    #finished = set()

    for e in events:
        method = e.get("method")
        p = e.get("params", {})

        if after:
            is_after = after
        else:
            is_after = e.get("_after", False)
        

        # ---------- REQUEST ----------
        if method == "Network.requestWillBeSent":
            rid = p["requestId"]
            r = p["request"]
            parsed = urlparse(r["url"])

            # POST body (best-effort)
            post_data = None
            if r["method"] != "GET":
                try:
                    post_data = driver.execute_cdp_cmd("Network.getRequestPostData", {"requestId": rid}).get("postData")
                except Exception as e:
                    post_data = None
            
            

            headers = None
            try:
                headers = r.get("headers")
            except Exception as e:
                headers = None

            inititator = None
            try:
                inititator = p.get("initiator")
            except Exception as e:
                inititator = None


            post_data = sanitize_text(post_data)
            headers = sanitize_text(headers)
            inititator = sanitize_text(inititator)

            req_rows.append((
                id_site,
                id_csv,
                country,
                run_no,
                choice,
                page_url,
                r["url"],
                r["method"],
                p.get("type"),
                headers,
                post_data,
                rid,
                inititator,
                is_after
            ))

        # ---------- REQUEST EXTRA ----------
        elif method == "Network.requestWillBeSentExtraInfo":
            headers = None
            cookies = None
            blocked_reasons = None

            try:
                headers = p.get("headers")
            except Exception as e:
                headers = None
            
            try:
                cookies = p.get("associatedCookies")
            except Exception as e:
                cookies = None

            try:
                blocked_reasons = p.get("blockedReasons")
            except Exception as e:
                blocked_reasons = None

            headers = sanitize_text(headers)
            cookies = sanitize_text(cookies)
            blocked_reasons = sanitize_text(blocked_reasons)

            req_extra.append((
                p["requestId"],
                id_site,
                id_csv,
                country,
                run_no,
                choice,
                headers,
                cookies,
                blocked_reasons
            ))

        # ---------- RESPONSE ----------
        elif method == "Network.responseReceived":
            rid = p["requestId"]
            resp = p["response"]

            url = None
            try:
                url = resp.get("url")
            except Exception:
                url = None

            body = None
            try:
                body = driver.execute_cdp_cmd("Network.getResponseBody",{"requestId": rid}).get("body")
            except Exception as e:
                body = None
            
            try:
                headers = resp.get("headers")
            except Exception as e:
                headers = None

            mime_type = None
            try:
                mime_type = resp.get("mimeType", "")
            except Exception as e:
                mime_type = None

            try:
                status_code = resp.get("status")
            except Exception as e:
                status_code = None

            try:
                status_text = resp.get("statusText")
            except Exception as e:
                status_text = None
            
            try:
                from_cache = bool(resp.get("fromDiskCache", False))
            except Exception as e:
                from_cache = None

            body = sanitize_text(body)
            mime_type = sanitize_text(mime_type)
            status_code = sanitize_text(status_code)
            status_text = sanitize_text(status_text)
            headers = sanitize_text(headers)

            res_rows.append((
                id_site,
                id_csv,
                country,
                run_no,
                choice,
                rid,
                url,
                status_code,
                status_text,
                headers,
                body,
                mime_type,
                from_cache,
                is_after
            ))
                
                #body = body_res.
                # base64_flag = body_res.get("base64Encoded", False)

                # if base64_flag and isinstance(raw_body, str):
                #     body = base64.b64decode(raw_body).decode("utf-8", errors="ignore")
                # else:
                #     body = raw_body

                # if isinstance(body, (dict, list)):
                #     body = json.dumps(body, ensure_ascii=False)
                # elif isinstance(body, bytes):
                #     body = body.decode("utf-8", errors="ignore")

                # if isinstance(body, str):
                #     body = strip_nul(body)

                # # --- parse JSON RIÊNG ---
                # body_json_parsed = None
                # if (
                #     body
                #     and isinstance(body, str)
                #    and resp.get("mimeType", "").startswith("application/json")
                #):
                #    try:
                #        body_json_parsed = safe_json_stream(body)
                #        #body_json = json.loads(body)
                #    except Exception:
                #        body_json_parsed = None
                #        #body_json = None


                # if resp.get("mimeType", "").startswith("application/json"):
                #     body_json_parsed = safe_json_stream(body)
                #     #body_json = json.loads(body)

            # except Exception as e:
            #     body = None
            #     body_json = None
            #     base64_flag = False
            #     body_json_parsed = None
                #if "No resource with given identifier" in str(e):
                #    body = None
                #    body_json = None
                #    base64_flag = False
                #else:
                #    print("rspR: ",e)
                #    pass



        # ---------- RESPONSE EXTRA ----------
        elif method == "Network.responseReceivedExtraInfo":
            rid = p["requestId"]

            try:
                headers = p.get("headers")
            except Exception as e:
                headers = None
            
            try:
                cookies = p.get("associatedCookies")
            except Exception as e:
                cookies = None
            
            try:
                blocked_reasons = p.get("blockedReasons")
            except Exception as e:
                blocked_reasons = None
            
            headers = sanitize_text(headers)
            cookies = sanitize_text(cookies)
            blocked_reasons = sanitize_text(blocked_reasons)

            res_extra.append((
                rid,
                id_site,
                id_csv,
                country,
                run_no,
                choice,
                headers,
                cookies,
                blocked_reasons
            ))
            
    # print("Request")
    # errs = debug_rows(req_rows)
    # for i, j, t, v in errs:
    #     print(f"[ERR] row={i}, col={j}, type={t}, value={v}")

    # print("Response")
    # errs = debug_rows(res_rows)
    # for i, j, t, v in errs:
    #     print(f"[ERR] row={i}, col={j}, type={t}, value={v}")
    
    # print("Request extra")
    # errs = debug_rows(req_extra)
    # for i, j, t, v in errs:
    #     print(f"[ERR] row={i}, col={j}, type={t}, value={v}")

    
    # print("Response extra")
    # errs = debug_rows(res_extra)
    # for i, j, t, v in errs:
    #     print(f"[ERR] row={i}, col={j}, type={t}, value={v}")


    #query_params, post_data_json
    with conn.cursor() as cur:

        psycopg2.extras.execute_values(cur, """
            INSERT INTO network_requests (
                id_site, id_csv, country, run_no, choice, page_url, request_url, method, resource_type,
                headers, post_data,
                cdp_request_id, initiator, is_after
            ) VALUES %s
        """, req_rows)

        # for r in res_rows:
        #     print(r)

        psycopg2.extras.execute_values(cur, """
            INSERT INTO network_responses (
                id_site, id_csv, country, run_no, choice, cdp_request_id, response_url, status_code, status_text,
                headers, response_body, mime_type, from_cache, is_after
            ) VALUES %s
        """, res_rows)

        psycopg2.extras.execute_values(cur, """
            INSERT INTO network_request_extra_info (
                cdp_request_id, id_site, id_csv, country, run_no, choice, headers, cookies, blocked_reasons
            ) VALUES %s
        """, req_extra)

        psycopg2.extras.execute_values(cur, """
            INSERT INTO network_response_extra_info (
                cdp_request_id, id_site, id_csv, country, run_no, choice, headers, cookies, blocked_reasons
            ) VALUES %s
        """, res_extra)


def save_network_AdsLanding_data(conn, id_site, page_url, events, after=False):
    req_map = {}   # CDP requestId -> DB request_id
    req_rows = []
    res_rows = []

    for e in events:
        method = e.get("method")
        params = e.get("params", {})

        # ---------------- REQUEST ----------------
        if method == "Network.requestWillBeSent":
            req_id = params.get("requestId")
            r = params.get("request", {})

            req_rows.append((
                id_site,
                to_text(page_url),
                to_text(r.get("url")),
                to_text(r.get("method")),
                to_text(params.get("type")),
                json.dumps(to_text(r.get("headers"))),
                json.dumps(to_text(r.get("postData"))),
                bool(after),
                None  # cookies
            ))

            req_map[req_id] = None

        # ---------------- RESPONSE ----------------
        elif method == "Network.responseReceived":
            resp = params.get("response", {})

            res_rows.append((
                params.get("requestId"),
                id_site,
                resp.get("status"),
                to_text(resp.get("statusText")),
                json.dumps(to_text(resp.get("headers"))),
                to_text(resp.get("mimeType")),
                bool(resp.get("fromDiskCache", False)),
                bool(after)
            ))

    with conn.cursor() as cur:

        # ---------- INSERT REQUESTS ----------
        if req_rows:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO network_requests (
                    id_site,
                    page_url,
                    request_url,
                    method,
                    resource_type,
                    headers,
                    payload,
                    is_after,
                    cookies
                )
                VALUES %s
                RETURNING request_id
                """,
                req_rows
            )

            db_ids = [r[0] for r in cur.fetchall()]
            for cdp_id, db_id in zip(req_map.keys(), db_ids):
                req_map[cdp_id] = db_id

        # ---------- INSERT RESPONSES ----------
        final_res_rows = []
        for r in res_rows:
            db_req_id = req_map.get(r[0])
            if db_req_id:
                final_res_rows.append((db_req_id, *r[1:]))

        if final_res_rows:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO network_responses (
                    request_id,
                    id_site,
                    status_code,
                    status_text,
                    headers,
                    mime_type,
                    from_cache,
                    is_after
                )
                VALUES %s
                """,
                final_res_rows
            )

def save_network_data(conn, id_site, run_id, page_url, events):
    req_map = {}   # CDP requestId -> DB request_id
    req_rows = []
    res_rows = []

    for e in events:
        method = e.get("method")
        params = e.get("params", {})

        # ---------------- REQUEST ----------------
        if method == "Network.requestWillBeSent":
            req_id = params.get("requestId")
            r = params.get("request", {})

            req_rows.append((
                id_site,
                run_id,
                to_text(page_url),
                to_text(r.get("url")),
                to_text(r.get("method")),
                to_text(params.get("type")),
                json.dumps(to_text(r.get("headers"))),
                json.dumps(to_text(r.get("postData"))),
                None  # cookies
            ))

            req_map[req_id] = None

        # ---------------- RESPONSE ----------------
        elif method == "Network.responseReceived":
            resp = params.get("response", {})

            res_rows.append((
                params.get("requestId"),
                id_site,
                run_id,
                resp.get("status"),
                to_text(resp.get("statusText")),
                json.dumps(to_text(resp.get("headers"))),
                to_text(resp.get("mimeType")),
                bool(resp.get("fromDiskCache", False))
            ))

    with conn.cursor() as cur:

        # ---------- INSERT REQUESTS ----------
        if req_rows:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO network_requests (
                    id_site,
                    run_id,
                    page_url,
                    request_url,
                    method,
                    resource_type,
                    headers,
                    payload,
                    cookies
                )
                VALUES %s
                RETURNING request_id
                """,
                req_rows
            )

            db_ids = [r[0] for r in cur.fetchall()]
            for cdp_id, db_id in zip(req_map.keys(), db_ids):
                req_map[cdp_id] = db_id

        # ---------- INSERT RESPONSES ----------
        final_res_rows = []
        for r in res_rows:
            db_req_id = req_map.get(r[0])
            if db_req_id:
                final_res_rows.append((db_req_id, *r[1:]))

        if final_res_rows:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO network_responses (
                    request_id,
                    id_site,
                    run_id,
                    status_code,
                    status_text,
                    headers,
                    mime_type,
                    from_cache
                )
                VALUES %s
                """,
                final_res_rows
            )


def write_crawl_result_to_db(
    url: str,
    mode: str,
    ip: str,
    page_title: str,
    events: list
):
    """
    CHỈ GHI DB
    - Không crawl
    - Không selenium
    - Không giữ connection lâu
    """

    domain = urlparse(url).netloc

    with get_db_conn() as conn:
        # ---------- SITE ----------
        id_site = insert_site(
            conn,
            domain_url=domain,
            profile=mode or "default",
            ip=ip,
            status="success"
        )

        # ---------- PAGE ----------
        page_id = upsert_page(
            conn,
            id_site=id_site,
            page_url=url,
            title=page_title
        )

        # ---------- RUN ----------
        run_id = insert_run(
            conn,
            id_site=id_site,
            page_id=page_id,
            page_url=url
        )

        # ---------- NETWORK ----------
        save_network_data(
            conn,
            id_site=id_site,
            run_id=run_id,
            page_url=url,
            events=events
        )

        # ---------- FINALIZE ----------
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE runs
                SET status='success',
                    run_end_time=NOW()
                WHERE run_id=%s
            """, (run_id,))

    return {
        "id_site": id_site,
        "page_id": page_id,
        "run_id": run_id,
        "requests": len(events)
    }


    
def insert_ads_information(
    conn,
    id_ads_element,
    id_site,
    run_id,
    ads_url,
    country,
    ads_company,
    platform,
    why_this_ads,
    more_info
):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ads_information (
                id_ads_element, id_site, run_id,
                ads_url, country, ads_company, ads_platform,
                why_this_ads, more_information
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            id_ads_element,
            id_site,
            run_id,
            ads_url,
            country,
            ads_company,
            platform,
            why_this_ads,
            more_info
        ))

def insert_consent_banner(conn, id_site, id_csv, country, run_no, domain_url, cmp_name, user_choice, html_snippet, more_information=None):
    """
    Insert one consent banner record into consent_banners table.

    user_choice must be one of:
    'accept', 'reject', 'custom', 'unknown'
    """

    print("HERE!!")

    # ---- Validate enum (IMPORTANT)
    valid_choices = {"accept", "reject", "not interacted", "custom", "unknown"}
    if user_choice not in valid_choices:
        user_choice = "unknown"

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO consent_banners (
                id_site,
                id_csv,
                country,
                run_no,
                domain_url,
                cmp_name,
                user_choice,
                html_snippet,
                more_information
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                id_site,
                id_csv,
                country,
                run_no,
                domain_url,
                cmp_name,
                user_choice,
                html_snippet,
                more_information
            )
        )
