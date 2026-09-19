from adblockparser import AdblockRules
import os
import tldextract

def load_rules(file_path, re2=False):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_rules = f.readlines()
    return AdblockRules(raw_rules, use_re2=re2)


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


def load_rules_from_folder(folder_path):
    all_rules = []

    for file in os.listdir(folder_path):
        if file.endswith(".txt"):
            full_path = os.path.join(folder_path, file)
            with open(full_path, "r", encoding="utf-8") as f:
                all_rules.extend(f.readlines())

    return AdblockRules(all_rules)

def is_tracking_from_urls(request, rules, page_url):
    domain_request = extract_reached_domain(request)
    domain_page = extract_reached_domain(page_url)
    is_3rd_party = False
    if domain_request.lower() != domain_page.lower():
        is_3rd_party = True

    options = {
        'script': True,
        'image': True,
        'xmlhttprequest': True,
        'domain': domain_page,
        'third-party': is_3rd_party
    }
    return rules.should_block(request, options)

def is_tracking(request, rules, domain_page, is_3rd_party):
    options = {
        'script': True,
        'image': True,
        'xmlhttprequest': True,
        'domain': domain_page,
        'third-party': is_3rd_party
    }
    return rules.should_block(request, options)

def is_tracking_domain(domain, rules, domain_page, is_3rd_party):
    f_url = f"http://{domain}/"
    options = {
        'domain': domain_page,
        'third-party': is_3rd_party
    }
    return rules.should_block(f_url, options)
