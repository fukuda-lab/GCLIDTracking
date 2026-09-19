#======PATCHNG RE2 ================
import re2
import re
import adblockparser.parser as parser


_original_compile = re2.compile

def compile_wrapper(pattern, flags=0, max_mem=None):
    return _original_compile(pattern)


re2.compile = compile_wrapper


def _combined_regex_chunked(regexes, flags=0, max_mem=None, use_re2=True, chunk_size=200, **kwargs):
    compiled = []

    for i in range(0, len(regexes), chunk_size):
        chunk = "|".join(f"(?:{r})" for r in regexes[i:i+chunk_size])

        try:
            if use_re2:
                compiled.append(re2.compile(chunk))
            else:
                compiled.append(re.compile(chunk, flags))
        except Exception as e:
            print(f"[WARN] chunk failed ({i}-{i+chunk_size}):", e)
            # fallback cực kỳ quan trọng
            compiled.append(re.compile(chunk, flags))

    return compiled


# override
parser._combined_regex = _combined_regex_chunked

from adblockparser import AdblockRules

def should_block_chunked(self, url):
    if any(r.search(url) for r in self.blacklist_re):
        return True
    return False

#AdblockRules.should_block = should_block_chunked


#from adblockparser import AdblockRules

from adblockparser import AdblockRules

def _matches_chunked(self, url, options, general_re, domain_re, rules_with_options):
    if general_re:
        if isinstance(general_re, list):
            for r in general_re:
                try:
                    if hasattr(r, "search"):
                        if r.search(url):
                            return True
                    else:
                        if r.match_url(url, options):
                            return True
                except ValueError:
                    continue
        else:
            if general_re.search(url):
                return True


    if domain_re and options and 'domain' in options:
        domain = options.get('domain')

        for dom, regex in domain_re.items():
            if domain.endswith(dom):

                # CASE 1: list
                if isinstance(regex, list):
                    for r in regex:
                        try:
                            if hasattr(r, "search"):
                                if r.search(url):
                                    return True
                            else:
                                if r.match_url(url, options):
                                    return True
                        except ValueError:
                            continue

                # CASE 2: regex object
                elif hasattr(regex, "search"):
                    if regex.search(url):
                        return True

                # CASE 3: AdblockRule
                else:
                    try:
                        if regex.match_url(url, options):
                            return True
                    except ValueError:
                        continue


    if rules_with_options:
        for rule in rules_with_options:
            try:
                if rule.match_url(url, options):
                    return True
            except ValueError:
                continue


    return False


AdblockRules._matches = _matches_chunked
#======END PATCHNG RE2 ================


from libs.checkTracking import load_rules, is_tracking
from libs.dbProcess import get_db_conn
import argparse
import tldextract
from psycopg2.extras import execute_values

def extract_reached_domain(url):
    if not url:
        #print("Not url: ",url)
        return ""

    try:
        ext = tldextract.extract(url)
        if not ext.domain or not ext.suffix:
            #print("Error :",url)
            return ""
        return f"{ext.domain}.{ext.suffix}"
    except Exception as e:
        #print("Error :",url)
        #print (e)
        return ""


def get_data_sites(conn):
    curr = conn.cursor()

    query = f"""
        SELECT DISTINCT id_csv
        FROM sites 
        WHERE crawl_status = 'success'
    """
    
    curr.execute(query)
    data = curr.fetchall()
    return data


def get_data_request_by_id_csv(conn, id_csv):
    curr = conn.cursor()

    query = f"""
        SELECT s.reached_url, s.id_csv, s.id_site, n.request_id, n.request_url, n.easylist, n.privacylist FROM sites s JOIN network_requests n 
        ON s.id_site = n.id_site
        WHERE s.id_csv = {id_csv}
        AND s.crawl_status = 'success'
        AND n.easylist IS NULL
        AND n.privacylist IS NULL
    """

    curr.execute(query)
    data = curr.fetchall()
    return data

def check_request(data, easylist_rules, easyprivacy_rules):
    res = []
    for row in data:
        url_reached = row[0]
        id_csv = row[1]
        id_site = row[2]
        request_id = row[3]
        request_url = row[4]

        request_domain = extract_reached_domain(request_url)
        reached_domain = extract_reached_domain(url_reached)

        if request_domain != "" and reached_domain != "" and request_domain.lower() != reached_domain.lower():
            is_third_party = True
        else:
            is_third_party = False

        try:
            is_tracker_easylist = is_tracking(request_url, easylist_rules, reached_domain, is_third_party)
            is_tracker_easyprivacy = is_tracking(request_url, easyprivacy_rules, reached_domain, is_third_party)                
        except Exception as e:
            print(f"Error occurred while checking request: {e}")

        
        res.append((request_id, id_csv, id_site, is_tracker_easylist, is_tracker_easyprivacy, is_third_party))
    return res


def update_request_tracking(conn, results):
    with conn.cursor() as cur:
        query = """
            UPDATE network_requests AS t
            SET 
                easylist = v.easylist,
                privacylist = v.privacylist,
                is_third_party = v.is_third_party
            FROM (VALUES %s) AS v(request_id, id_csv, id_site, easylist, privacylist, is_third_party)
            WHERE 
                t.request_id = v.request_id
                AND t.id_csv = v.id_csv
                AND t.id_site = v.id_site
        """
        execute_values(cur, query, results)
    conn.commit()



def run_main(easylist_rules, easyprivacy_rules):
    with get_db_conn() as conn:
        data_sites = get_data_sites(conn)
    
    for row_site in data_sites:
        print(f"Processing id_csv: {row_site[0]}")
        id_csv = row_site[0]
        with get_db_conn() as conn:
            data = get_data_request_by_id_csv(conn, id_csv)
            
        if data:
            results = check_request(data, easylist_rules, easyprivacy_rules)
    
            with get_db_conn() as conn:
                update_request_tracking(conn, results)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch Data Processing - Check Tracker EasyList/PrivacyList")
    parser.add_argument("--re2", action="store_true", help="Use re2 engine for adblock rules (default: False)")

    args = parser.parse_args()

    easylist_rules = load_rules("extensions/DetectAds/rules/easylist.txt", re2=args.re2)
    easyprivacy_rules = load_rules("extensions/DetectAds/rules/easyprivacy.txt", re2=args.re2)

    run_main(easylist_rules, easyprivacy_rules)
