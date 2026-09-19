import random
import time
import openai
import threading
import traceback

from PIL import Image


import traceback
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

from libs.dbProcess import get_db_conn, insert_consent_banner, save_cookies_pg, save_local_storage_pg, save_session_storage_pg, save_full_network_data_AdsLanding
from libs.process import performance_log_listener
from libs.helpers import is_infinite_scroll_page, scroll_infinite, slow_scroll_page, smart_delay
from libs.getStorage import getLocalStorage, getSessionStorage

from inspect import currentframe


try:
    from .utility.utilityMethods import *
except ImportError:
    try:
        from utility.utilityMethods import *
    except ImportError:
        raise ImportError("Failed to import utilityMethods")

try:
    from .config import *
except ImportError:
    try:
        from config import *
    except ImportError:
        raise ImportError("Failed to import config")


from .subscriptiondetection import sub_detection


from selenium import webdriver
from selenium.webdriver.chrome.service import Service


rej_flag = False
GPT_USED = 0


def is_semantically_correct_gpt(el, semantic):
    try:
        openai.api_key = API_KEY
        button_element = el.get_attribute("outerHTML")
        prompt = """
            You are a web scraping assistant. Given the following HTML content, if you think the following HTML element could be semantically related to a {semantic} button (regarding web cookies) return "yes" otherwise return "no".
            html element:
            {button_element}
            
            Return "yes" or "no".
            """.format(semantic=semantic, button_element=button_element)

        model = "gpt-4o-mini"
        # Call GPT-4 to get the XPath
        response = openai.ChatCompletion.create(
            model=model,  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are an expert in analyzing HTML for web scraping purposes."},
                {"role": "user", "content": prompt},
            ]
        )

        res = response['choices'][0]['message']['content'].strip()
        return "yes" in res
    except:
        return None


def remove_els_with_gpt(els: list[WebElement], choice):
    to_remove = []
    for el in els:
        if choice == 1:
            res = is_semantically_correct_gpt(el, semantic="positive")
            if not res and res is not None:
                to_remove.append(el)
    entries_to_remove(to_remove, els)




# Step 1: Initialize GPT-4 to find the reject button
def find_reject_button_html_gpt(html_content):
    try:
        openai.api_key = API_KEY

        prompt = """
        You are a web scraping assistant. Given the following HTML content, identify the XPath of the "Reject" or "Decline" button typically found in cookie consent banners.
        HTML:
        {html_content}
        Return "JUST" XPath for the "Reject" button with no explanation. Put the XPath between ";".
        """.format(html_content=html_content)

        model = "gpt-4o-mini"
        # Call GPT-4 to get the XPath
        response = openai.ChatCompletion.create(
            model=model,  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are an expert in analyzing HTML for web scraping purposes."},
                {"role": "user", "content": prompt},
            ]
        )
        xpath = response['choices'][0]['message']['content'].strip(";")
        return xpath
    except:
        return None


def get_btns_gpt(el, choice):
    buttons = []
    html = to_html(el)
    if len(html) > 10000:
        html = extract_essential_html(html)
    html = extract_essential_html(html)
    xpath = find_btns_xpath_gpt(html, choice)
    if "not found" not in xpath:
        try:
            buttons = WebDriverWait(el, 2).until(
                EC.presence_of_all_elements_located((By.XPATH, xpath))
            )
            pruning_btns(buttons)
        except Exception as ex:
            pass
    return buttons

def find_btns_xpath_gpt(html_content, choice):
    global  rej_flag
    openai.api_key = API_KEY

    if choice == 2:
        if rej_flag:
            prompt = """
            I have clicked on the settings button of a cookie banner. Below is the current HTML DOM of the cookie banner. Your task is to search the DOM and identify the possible XPath of elements that related to buttons which either "confirm" the current selected preferences or "reject all" non-essential cookies, leading to the closing of the banner. Avoid selecting buttons related to "accepting all" cookies.
            HTML:
            {html_content}

            If such elements exist in the above DOM, return their XPath (separated by | if multiple), otherwise, return "not found" and nothing else.
            
            (if you found the xpaths of the elements:
            your response is possibly correct if its text contains something similar to: "Save and Exit", "Submit preferences", "Reject All", "Accept selected" or any thing semantically related
            your response is possibly wrong if its text contains something similar to: "Accept All", "Manage Settings", "More Information", "Return" or any thing semantically related)
            """.format(html_content=html_content)
        else:
            prompt = """
            You are a web scraping assistant, please ANSWER following query. Below is the HTML DOM of a cookie banner. Identify the XPath of buttons that either "refuse" or "reject all" non-essential cookies, leading to the closing of the banner. Avoid selecting buttons related to "accepting all" cookies or "settings" of cookie banners.
    
            HTML:
            {html_content}

            If you find such buttons in the DOM, return their XPath (separated by | if multiple). If not, return "not found" and nothing else.
            
            (if you found the xpaths of the elements:
            your response is possibly correct if its text contains something similar to: "reject", "disagree", "do not agree", "continue without accept", "only essential" or any thing semantically related
            your response is possibly wrong if its text contains something similar to:  "Accept All", "Manage Settings", "More Information", "dismiss", "Adjust", "ok" or cross sign (X) resulting in implicitly accepting the banner or any thing semantically related)
            """.format(html_content=html_content)
    elif choice == 3:
        prompt = """
        You are a web scraping assistant, please ANSWER following query. Below is the HTML DOM of a cookie banner. Identify the XPath of buttons that is related to "settings" or "options" of the cookies, leading to the opening cookie banner setting. Avoid selecting buttons related to "accepting" or "rejecting" cookies.
        (the text in the xpath "ANSWER" might be similar as: "Manage Settings", "More Information", "More Preferences" or any thing semantically related
        example of wrong ANSWER are: buttons text contains "Accept All", "Reject all", "Deny", "Privacy Policy" or any thing semantically related)
        HTML:
        {html_content}

        If you find such buttons in the DOM, return their XPath (separated by | if multiple). If not, return "not found" and nothing else.
        """.format(html_content=html_content)
    try:
        model = "gpt-4o-mini"
        # Call GPT-4 to get the XPath
        response = openai.ChatCompletion.create(
            model=model,  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are an expert in analyzing HTML for web scraping purposes."},
                {"role": "user", "content": prompt},
            ]
        )
    except:
        return "not found"
    try:
        res = response['choices'][0]['message']['content']
        res = res.replace("```", "").replace("xpath", "").replace("\n", "")
        return res.strip('"')
        # if not ("xpath" in res or "'''" in res):
        #     return res.strip('"')
        pattern = r"/.*?\](?!.*\])"
        matches = re.findall(pattern, res)
        xpath = ""
        first_flag = False
        # Check if any matches were found and print them
        if matches:
            for match in matches:
                if first_flag:
                    xpath += " | "
                xpath += match
                first_flag = True
            return xpath
        else:
            return "not found"
    except:
        return "not found"


def is_sub_gpt(html_content):
    try:

        openai.api_key = API_KEY
        prompt = """
        You are a web scraping assistant. Given the following HTML content, identify if the following HTML dom is related to a cookie paywall banner.
        HTML:
        {html_content}
           Just return "yes" if it is cookie paywall and "no" otherwise.
        """.format(html_content=html_content)

        model = "gpt-4o-mini"
        # Call GPT-4 to get the XPath
        response = openai.ChatCompletion.create(
            model=model,  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are an expert in analyzing HTML for web scraping purposes."},
                {"role": "user", "content": prompt},
            ]
        )

        res = response['choices'][0]['message']['content'].strip()
        return "yes" in res
    except Exception as ex:
        return None




def reset(driver):
    global counter, visit_db, domains, this_domain, this_url, banner_db, html_db, this_lang, this_banner_lang, this_run_url
    counter = 0
    driver = None
    visit_db = None
    banner_db = None
    html_db = None
    domains = []
    this_domain = None
    this_url = None
    this_run_url = None
    this_lang = None
    this_banner_lang = None



def set_zoom(driver, zoom_level):
    # Ensure the zoom level is a decimal like 0.8 for 80%, 1.0 for 100%, etc.
    driver.execute_script(f"document.body.style.zoom='{zoom_level}';")




def get_data_dir_name():
    global data_dir
    return data_dir


def set_data_dir_name(dir_name):
    global data_dir
    data_dir = dir_name

def init_pc(headless=HEADLESS, input_file=None, num_browsers=NUM_BROWSERS, num_repetitions=1, domains_file=None, v_db=None,
         b_db=None, h_db=None):  # initialize bannerdetection by setting url file and webdriver instance
    global domains, file, input_files_dir, UBLOCK_ADDON
    url_dir = "./input-files/"
    if domains_file is None:
        file = url_dir+urls_file
    else:
        file = url_dir+domains_file
    create_data_dirs()
    if os.path.isfile(file):
        domains = file_to_list(file)
    # set_database(v_db, b_db, h_db)

    if input_file:
        file = input_file
    init_str = f"""Crawl initialized for: {file} in {datetime.now().strftime("%H-%M-%S").__str__()}
    START_POINT:STEP_SIZE: {START_POINT}:{STEP_SIZE}
    headless: {headless}
    input_file: {input_file}
    num_browsers: {num_browsers}
    num_repetitions: {num_repetitions}
    timeout: {TIME_OUT}
    translation: {TRANSLATION}
    delay_time: {SLEEP_TIME}
    ATTEMPTS:ATTEMPT_STEP: {ATTEMPTS}:{ATTEMPT_STEP}
    Chrome: {CHROME}
    openwpm.xpi: {XPI}
    Watchdog: {WATCHDOG}
    interaction choice: {"ALL"}
    non explicit: {NON_EXPLICIT}
    SIMPLE_DETECTION: {SIMPLE_DETECTION}
    search for reject btn in setting: {REJ_IN_SET}
    NC_ADDON: {NC_ADDON}
    mobile agent: {MOBILE_AGENT}
    CMP detection: {CMPDETECTION}
    banner interaction: {BANNERINTERACTION} \n\n""" + "__"*30 + "\n"
    print(init_str)

    try:
        with open(log_file, 'a+') as f:
            print(init_str, file=f)
    except:
        pass


def init_ONE_pc(headless=HEADLESS, v_db=None, b_db=None, h_db=None, domain=None, dir=None):  # initialize bannerdetection by setting url file and webdriver instance
    create_data_dirs_MOD(dir)
    #set_database(v_db, b_db, h_db)


    init_str = f"""Crawl initialized for: {domain} in {datetime.now().strftime("%H-%M-%S").__str__()}
    START_POINT:STEP_SIZE: {START_POINT}:{STEP_SIZE}
    headless: {headless}
    timeout: {TIME_OUT}
    translation: {TRANSLATION}
    delay_time: {SLEEP_TIME}
    ATTEMPTS:ATTEMPT_STEP: {ATTEMPTS}:{ATTEMPT_STEP}
    Chrome: {CHROME}
    Watchdog: {WATCHDOG}
    interaction choice: {"ALL"}
    non explicit: {NON_EXPLICIT}
    SIMPLE_DETECTION: {SIMPLE_DETECTION}
    search for reject btn in setting: {REJ_IN_SET}
    NC_ADDON: {NC_ADDON}
    mobile agent: {MOBILE_AGENT}
    CMP detection: {CMPDETECTION}
    banner interaction: {BANNERINTERACTION} \n\n""" + "__"*30 + "\n"
    #print(init_str)

    #print(log_file)

    #try:
    #    with open(log_file, 'a+') as f:
    #        print(init_str, file=f)
    #except:
    #    pass



def get_domains():
    global domains
    return domains


def create_data_dirs_MOD(dir):
    global data_dir, sc_dir, nobanner_sc_dir, log_file, banners_log_file, season_dir, sc_file_name

    season_dir = dir + run_name + "/"
    data_dir = season_dir + time_dir
    sc_dir = data_dir + "/banner_screenshots/"
    nobanner_sc_dir = sc_dir + "nobanner/"
    sc_file_name = ""
    log_file = data_dir + '/logs.txt'
    banners_log_file = data_dir + '/banners_log.txt'


    if not os.path.exists(season_dir):
        os.makedirs(season_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    if not os.path.exists(sc_dir):
        os.makedirs(sc_dir)
    if not os.path.exists(nobanner_sc_dir):
        os.makedirs(nobanner_sc_dir)


def create_data_dirs():
    if not os.path.exists(season_dir):
        os.makedirs(season_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    if not os.path.exists(sc_dir):
        os.makedirs(sc_dir)
    if not os.path.exists(nobanner_sc_dir):
        os.makedirs(nobanner_sc_dir)


def file_to_list(target_file_name):
    global domains, STEP_SIZE
    if ".csv" in target_file_name:
        sites_csv = pd.read_csv(target_file_name)
        num_rows = sites_csv.shape[0]

        # read from .csv file. from START_POINT to START_POINT + STEP_SIZE
        if num_rows < STEP_SIZE:
             STEP_SIZE = num_rows
        domains = [
            make_url(sites_csv.iloc[row].domain)
            for row in range(START_POINT, START_POINT + STEP_SIZE)
        ]

    else:
        file = set_urls_file(target_file_name)

        while True:
            domain = file.readline().strip('\n')
            if not domain:
                break
            if domain == "#":
                break
                # continue
            if domain == "$":
                break
            domains.append(domain)
    return domains


def set_database(v_db, b_db, h_db):
    global visit_db, banner_db, html_db
    if v_db is None:
        visit_db = pd.DataFrame({
            'visit_id': pd.Series([], dtype='int'),
            'domain': pd.Series([], dtype='str'),
            'url': pd.Series([], dtype='str'),
            'run_url': pd.Series([], dtype='str'),
            'status': pd.Series([], dtype='int'),
                    'btn_status': pd.Series([], dtype='int'),
            'lang': pd.Series([], dtype='str'),
            'banners': pd.Series([], dtype='int'),
            'ttw': pd.Series([], dtype='int'),
            '__cmp': pd.Series([], dtype='bool'),
            '__tcfapi': pd.Series([], dtype='bool'),
            '__tcfapiLocator': pd.Series([], dtype='bool'),
            'cmp_id': pd.Series([], dtype='int'),
            'cmp_name': pd.Series([], dtype='str'),
            'pv': pd.Series([], dtype='bool'),
            'dnsmpi': pd.Series([], dtype='str'),
            'body_html': pd.Series([], dtype='str'),
        })
        banner_db = pd.DataFrame({
            'banner_id': pd.Series([], dtype='int'),
            'visit_id': pd.Series([], dtype='int'),
            'domain': pd.Series([], dtype='str'),
            'lang': pd.Series([], dtype='str'),
            'iFrame': pd.Series([], dtype='bool'),
            'shadow_dom': pd.Series([], dtype='bool'),
            'captured_area': pd.Series([], dtype='float'),
            'x': pd.Series([], dtype='float'),
            'y': pd.Series([], dtype='float'),
            'w': pd.Series([], dtype='float'),
            'h': pd.Series([], dtype='float'),
        })
        html_db = pd.DataFrame({
            'banner_id': pd.Series([], dtype='int'),
            'visit_id': pd.Series([], dtype='int'),
            'domain': pd.Series([], dtype='str'),
            'html': pd.Series([], dtype='str'),
        })
    else:
        visit_db = v_db
        banner_db = b_db
        html_db = h_db
    return visit_db, banner_db, html_db


def get_database():
    global visit_db, banner_db, html_db
    return visit_db, banner_db, html_db


def find_cookie_banners(driver, origin_el=None, translate=False, stale_flag=False, safari = False):
    # TODO: WITHOUT EXCEPTION HANDLING
    global this_lang
    try:
        banners = []
        banners_map = dict()

        if origin_el is None:
            wait = WebDriverWait(driver, 20)
            body_el = wait.until(
                ec.visibility_of_element_located((By.TAG_NAME, "body")))
            # set_zoom(driver, 0.7)
            time.sleep(0.2)
            WebDriverWait(driver, 5).until(lambda d: d.execute_script(
                'return document.readyState') == 'complete')
            # body_el = driver.find_element(By.TAG_NAME, "body")
            origin_el = body_el
            shadowdom_flag = False
        else:
            shadowdom_flag = True
        if translate:
            detected_lang = this_lang
            els_with_cookie = find_els_with_cookie(origin_el, detected_lang, safari=safari)
        else:
            detected_lang = "en"
            # find all the element with cookies related words
            els_with_cookie = find_els_with_cookie(origin_el, safari=safari)
        
        if els_with_cookie:
            #if safari:
            #    print(f"[Line {currentframe().f_back.f_lineno}]:", "SAFARI - [LOG] Detected cookie banner")
            banners_map = find_fixed_ancestors(els_with_cookie, safari=safari)

            if not banners_map:
                banners_map = find_by_zindex(els_with_cookie, safari=safari)
            if not banners_map:
                banners_map[origin_el] = find_deepest_el(els_with_cookie, safari=safari)
            for item in banners_map.items():
                optimal_el = find_optimal(driver, item, safari=safari)
                
                if is_inside_viewport(optimal_el, safari=safari) and has_enough_word(optimal_el) and not is_signin_banner(optimal_el):
                    banners.append(optimal_el)
        
        # check all the iframes to detect cookie banners
        #print("Checking iframes for cookie banners...")
        frame_pairs = find_CMP_cookies_iframes(driver, detected_lang)
        #print("Found {} iframe candidates.".format(len(frame_pairs)))
        
        for frame_pair in frame_pairs:
            # check if the banner is in viewport
            if is_inside_viewport(frame_pair[0]):
                banners.append(frame_pair)
        #print("Total banners found so far: ", len(banners))
        if not banners and not shadowdom_flag:
            shadowdom_banners = find_shadowdom_banners(driver, safari=safari)
            for dom_pair in shadowdom_banners:
                banners.append(dom_pair)
                # if is_inside_viewport(dom_pair[0]):  # check if the banner is in viewport

        return banners
    except StaleElementReferenceException as e:  # handle specific exception
        time.sleep(1)
        if not stale_flag:
            return find_cookie_banners(driver,stale_flag=True, safari=safari)
        raise e
    except Exception as e:  # Catch any other exceptions
        print(f"An error occurred in find_cookie_banners: {e}")
        raise e
    
        # return banners


def find_shadowdom_banners(driver, safari = False):
    banners = []
    # root_copy_pairs_js = add_shadow_dom_to_body(driver)
    root_copy_pairs = add_shadow_dom_to_body(driver)
    for root_copy_pair in root_copy_pairs:
        shadow_dom_banner = find_cookie_banners(driver, origin_el=root_copy_pair[1], safari=safari)
        if shadow_dom_banner:
            banners.append((root_copy_pair[0], shadow_dom_banner[0]))

    return banners


def detect_banners(driver, data, safari = False):  # return banners of the current running url
    global this_url, this_domain, this_status, visit_db, this_lang, this_index
    banners = []
    inc_counter()
    try:
        if ZOOMING:
            zoom_out(3)
        if not data.url:
            return banners
        this_index = data.index
        this_url = data.url
        this_domain = data.domain
        this_lang = None
        time.sleep(2.5)
        banners = find_cookie_banners(driver, safari=safari)

        # with open(banners_log_file, 'a+') as f:
        #     init_str = this_domain + " banner detection finished within: " + str(
        #         completion_time.microseconds)
        #     print(init_str, file=f)

        this_lang = page_lang(driver)
        data.lang = this_lang
        if ATTEMPTS:
            for att in range(ATTEMPTS):
                if banners:
                    break
                time.sleep(ATTEMPT_STEP)
                if not banners:
                    banners = find_cookie_banners(driver, safari=safari)
                else:
                    return banners
                data.ttw = (att + 1) * ATTEMPT_STEP
        if not banners and TRANSLATION:
            # if no banner is found and the language of site is not english then translate the page and check again
            if "en" not in this_lang and is_in_langlist(this_lang):
                translate_page(driver)
                banners = find_cookie_banners(driver, translate=True, safari=safari)
                this_status = 3
                data.status = this_status
    except Exception as ex:
        with open(log_file, 'a+') as f:
            print("failed to continue detecting banner for domain: " +
                  data.domain + " " + ex.__str__(), file=f)
            # MyExceptionLogger(err=ex, file=f)
        this_status = -1
        data.status = this_status
    return banners


def interact_with_cmp_banner(driver, el: WebElement):
    global MODIFIED_ADDON
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # never_consent_extension_win_path = r'C:\Users\arasaii\AppData\Roaming\Mozilla\Firefox\Profiles\jf3srcbq.cookiesprofile\extensions\{816c90e6-757f-4453-a84f-362ff989f3e2}.xpi'  # Must be the full path to an XPI file!
    # Must be the full path to an XPI file!
    never_consent_extension_win_path = r'C:\Drives\Education\MPI\Intern\Codes\Workstation\bannerdetection\neverconsent\neverconsent.xpi'
    never_consent_extension_path = current_dir + "/neverconsent/neverconsent.xpi"

    # Neu MODIFED_ADDON = True
    #   Run script '../neverconsent/nc.js'    
    if MODIFIED_ADDON:
        run_addon_js(driver)

    
    # Neu MODIFIED_ADDON = False
    #   (1) Install Addon neverconsent.xpi
    #   (2) Remove Addon

    # (1)
    else:
        try:
            id = driver.install_addon(
                never_consent_extension_path, temporary=True)
        except:
            id = driver.install_addon(
                never_consent_extension_win_path, temporary=True)
    time.sleep(2)

    # (2)
    # Neu MODIFIED_ADDON = False
    if not MODIFIED_ADDON:
        driver.uninstall_addon(id)

    
    try:
        if el.is_displayed():
            return False
        else:
            return True
    except Exception as E:
        return True


def interact_with_gpt(driver, el, file_name, choice=2):
    global GPT_USED
    try:
        flag = False
        # Wait for the button to be present and visible
        btns = get_btns_gpt(el, choice)
        if btns:
            flag = click_func(driver, el, btns, file_name, SCREENSHOT)
            if GPT_USED:
                GPT_USED = 6
            else:
                GPT_USED = -6
        return flag

    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def interact_with_banner(driver, banner_item, banners_data, choice, status, i, total_search=False, safari=False):
    global this_index, NON_EXPLICIT, rej_flag, NC_ADDON, SIMPLE_DETECTION, SCREENSHOT, GPT_USED
    flag = False
    addon_interaction = False
    gpt_interaction = False
    gpt_setting_interaction = False
    explicit_coeff = 1
    html = ""
    this_banner_lang = "en"

    try:
        this_banner_lang = banners_data[i].get('lang', "en")
        html = banners_data[i].get('html_short', "")
        if banners_data[i].get('is_sub', False) and choice == 2:
            return False
    except:
        pass

    try:
        WebDriverWait(driver, 1).until(lambda d: d.execute_script(
            'return document.readyState') == 'complete')
    except:
        try:
            driver.switch_to.default_content()
            WebDriverWait(driver, 0.5).until(lambda d: d.execute_script(
                'return document.readyState') == 'complete')
        except:
            return False

    try:
        banner, shadow_host = get_banner_obj(driver, banner_item)
    except Exception as ex:
        driver.switch_to.default_content()
        return
    try:
        body_el = driver.find_element(By.TAG_NAME, "body")
        if total_search:       # search the whole body DOM for the words, this is because sometimes for example after clicking on setting the banner DOM disappears or the page redirect to another page.
            el = body_el
        else:
            el = banner
    except:
        return False

    try:
        file_name = create_btn_filename(driver, choice, i)

        ex_btns = extract_btns(el, choice, shadow_root=shadow_host)
        if choice == 2 and rej_flag and len(ex_btns) > 3:
            keep_els_with_words(
                ex_btns, ['all'], this_banner_lang, check_attr=False)
        ex_btns_temp = list(ex_btns)
        if SIMPLE_DETECTION or choice != 2 or rej_flag:
            flag = click_func(driver, el, ex_btns, file_name, SCREENSHOT, safari=safari)
            if not flag and NON_EXPLICIT:
                nex_btns = extract_btns(
                    el, choice, shadow_root=shadow_host, non_explicit=True)
                entries_to_remove(ex_btns_temp, nex_btns)
                flag = click_func(driver, el, nex_btns, file_name, SCREENSHOT, safari=safari)
                explicit_coeff = -1
            if rej_flag and (not flag or is_availble(driver, el)) and GPT_ENABLE:  # user gpt iteraction if the button is not cliked or is still visible or enable
                file_name = create_btn_filename(8, i)
                gpt_setting_interaction = interact_with_gpt(driver, el, file_name, choice)
                if gpt_setting_interaction:
                    flag = False

        if choice == 2 and not flag and not rej_flag:
            if NC_ADDON:
                addon_interaction = interact_with_cmp_banner(el)

            if REJ_IN_SET and not addon_interaction:
                set_flag = interact_with_banner(el, banners_data, 3, status, i, safari=safari)
                if set_flag:
                    time.sleep(1)
                    rej_flag = True
                    is_total_search = False
                    # this total_search causes click on wrong reject btns like: statista.com, politico.com, sap.com
                    if not is_availble(driver, el):
                        is_total_search = True
                    flag = interact_with_banner(
                        el, banners_data, choice, status, i, is_total_search, safari=safari)
                    if not flag:
                        is_total_search = True
                        flag = interact_with_banner(
                            el, banners_data, choice, status, i, is_total_search, safari=safari)
                    if not flag:
                        try:
                            driver.switch_to.default_content()
                            iframes = get_iframes(driver)
                            iframes.reverse()
                            for iframe in iframes:
                                try:
                                    driver.switch_to.default_content()
                                    driver.switch_to.frame(iframe)
                                    flag = interact_with_banner(
                                        el, banners_data, choice, status, i, is_total_search, safari=safari)
                                    if flag:
                                        break
                                except:
                                    pass
                        except:
                            pass


        if type(banner_item) is tuple:
            driver.switch_to.default_content()
        if flag:
            time.sleep(0.1)
            if choice == 1 or choice == 2:
                driver.switch_to.default_content()
                status['btn_status'] = choice * explicit_coeff
                take_current_page_sc(suffix=suffix(
                    choice) + "_after" + str(i + 1))
            elif choice == 3:
                status['btn_set_status'] = choice * explicit_coeff
                take_current_page_sc(suffix=suffix(
                    choice) + "_after" + str(i + 1))
            if shadow_host:
                del_cloned_shadow_hosts(driver)
        if addon_interaction:
            status['btn_set_status'] = 1
            take_current_page_sc(suffix="_Xnc_after" + str(i + 1))
        if gpt_interaction:
            status['btn_status'] = choice
            status['btn_set_status'] = 2
            take_current_page_sc(suffix="_Xgpt_after" + str(i + 1))
        if gpt_setting_interaction:
            driver.switch_to.default_content()
            status['btn_set_status'] = -1
            take_current_page_sc(suffix="_XXgptrejINset_after" + str(i + 1))

    except Exception as ex:
        try:
            driver.switch_to.default_content()
        except:
            pass
    # status['gpt_usage'] = GPT_USED
    return flag

def extract_btns(element, choice, shadow_root=None, non_explicit=False):
    global this_banner_lang, rej_flag, GPT_USED
    if choice == 1:
        btns = find_btns_by_list(
            element, accept_words, this_banner_lang, non_explicit)
        remove_els_with_words(btns, non_acceptable, this_banner_lang)
    elif choice == 2:
        if rej_flag:
            rej_words = reject_setting_words
            if non_explicit:
                return []
        else:
            rej_words = reject_words
        btns = find_btns_by_list(
            element, rej_words, this_banner_lang, non_explicit)
        if btns and non_explicit:
            remove_els_with_words(btns, accept_words, this_banner_lang, False)
        if not btns and not non_explicit:
            btns = find_btns_by_list(
                element, accept_words, this_banner_lang, non_explicit)
            keep_els_with_words(btns, non_acceptable, this_banner_lang)
            if not btns and GPT_REJ and not rej_flag and GPT_ENABLE:
                btns = get_btns_gpt(element, choice)
                if btns:
                    GPT_USED = 2
    elif choice == 3:
        words = list(setting_words)
        if not non_explicit:
            words.extend(more_setting_words)
        btns = find_btns_by_list(
            element, words, this_banner_lang, non_explicit)
        if not btns and not non_explicit and GPT_ENABLE:
            btns = get_btns_gpt(element, choice)
            if btns:
                GPT_USED = 3
    elif choice == 4:
        btns = find_btns_by_list(element, login_words,
                                 this_banner_lang, non_explicit)
    if PRUNE_GPT:
        remove_els_with_gpt(btns, choice)
    if shadow_root is not None:
        btns = get_els_from_root(shadow_root, btns)
    return btns


def suffix(choice):
    global rej_flag
    if choice == 1:
        return "_XX" + 'acc'
    elif choice == 2:
        return "_XX" + 'rej' + ('INset' if rej_flag else '')
    elif choice == 3:
        return "_X" + 'set'
    elif choice == 4:
        return "_X" + 'log'
    elif choice == 5:
        return "_XX" + 'conbtn'
    elif choice == 6:
        return "_X" + 'log'
    elif choice == 7:
        return "_XX" + 'login'
    elif choice == 8:
        return "_XX" + 'gptrej' + ('INset' if rej_flag else '')


def create_btn_filename(driver, choice, i):
    global this_index
    return sc_dir + get_sc_file_name(driver, this_index) + suffix(choice) + "_" + str(i + 1)


def get_banner_obj(driver, banner_item):
    shadow_host = None
    if type(banner_item) is tuple:
        frame = banner_item[0]
        banner = banner_item[1]
        try:
            driver.switch_to.frame(frame)
            if type(banner) is tuple:
                frame = banner[0]
                banner = banner[1]
                driver.switch_to.frame(frame)
        except:  # for shadow root
            banner = banner_item[1]
            shadow_host = banner_item[0]
    else:
        banner = banner_item
    return banner, shadow_host


def get_sc_file_name(driver, index=None, url=None):
    global visit_db, this_url
    if url is None:
        url = this_url
    if index is None:
        return str(visit_db.shape[0]) + " " + get_current_domain(driver, url)
    else:
        return str(index+1) + " " + get_current_domain(driver, url)


def take_current_page_sc(driver, data=None, directory=None, suffix=""):
    global SCREENSHOT
    if SCREENSHOT:
        if data is None:
            index = this_index
            url = this_url
        else:
            index = data.index
            url = data.url
        if directory is None:
            directory = sc_dir
        try:
            driver.save_screenshot(
                directory + get_sc_file_name(driver, index, url) + suffix + ".png")
        except Exception as ex:
            if "cross-origin" in  ex.__str__():
                try:
                    driver.switch_to.default_content()
                    driver.save_screenshot(
                        directory + get_sc_file_name(driver, index, url) + suffix + ".png")
                    return
                except Exception as ex:
                    pass
            with open(log_file, 'a+') as f:
                print("failed to take screenshot for url: " +
                      url + " " + ex.__str__(), file=f)


def inc_counter():
    global counter
    counter += 1


def take_banner_sc(driver, banner_item, data, j=None):
    if banner_item:
        try:
            banner, _ = get_banner_obj(banner_item)
        except Exception as ex:
            print("1. failed in switching frame for : " + this_url + " in take_banner_sc. " + ex.__str__())
            return
        
        
        try:
            if j is not None:
                if CHROME:
                    # chrome does not have built-in function for taking screenshot of an element.
                    chrome_element_sc(banner, data.index, j)
                else:
                    banner.screenshot(
                        sc_dir + get_sc_file_name(driver, this_index) + "_banner" + str(j + 1) + ".png")
            else:
                banner.screenshot(
                    sc_dir + get_sc_file_name(driver, this_index) + "_banner" + ".png")
            
            if type(banner_item) is tuple:
                driver.switch_to.default_content()
        except Exception as ex:
            print("2. failed in switching frame for : " + this_url + " in take_banner_sc. " + ex.__str__())
        return banner


def chrome_element_sc(driver, banner, index, j):
    location = banner.location
    size = banner.size
    ax = location['x']
    ay = location['y']
    width = location['x'] + size['width']
    height = location['y'] + size['height']
    crop_image = Image.open(sc_dir + get_sc_file_name(driver, index) + ".png")
    crop_image = crop_image.crop((int(ax), int(ay), int(width), int(height)))
    crop_image.save(sc_dir + get_sc_file_name(driver, index) +
                    "_banner" + str(j + 1) + "_ch.png")


def is_sub(text, html):
    if SUB_DETECTION:
        tuple = sub_detection(text, html)
        if tuple:
            if GPT_ENABLE and GPT_SUB:
                is_sub = is_sub_gpt(text)
                if is_sub or is_sub is None:
                    return True
            else:
                return True
        else:
            return False
    return False

import html.parser
class EssentialHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.essential_html = ""
        self.in_footer = False
        self.in_img = False
        self.in_script = False
        self.in_hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in ['footer', 'img', 'script', 'hidden']:
            self.in_footer = tag == 'footer'
            self.in_img = tag == 'img'
            self.in_script = tag == 'script'
            self.in_hidden = tag == 'hidden'
            return

        if not self.in_footer and not self.in_img and not self.in_script and not self.in_hidden:
            attributes = []
            for attr, value in attrs:
                if attr in ['id', 'name']:
                    attributes.append(f'{attr}="{value}"')
                elif attr == 'class' and ('btn' in value or 'button' in value):
                    attributes.append(f'{attr}="{value}"')

            self.essential_html += f"<{tag} {' '.join(attributes)}>".replace(" ", " ")

    def handle_endtag(self, tag):
        if tag in ['footer', 'img', 'script', 'hidden']:
            self.in_footer = False
            self.in_img = False
            self.in_script = False
            self.in_hidden = False
            return

        if not self.in_footer and not self.in_img and not self.in_script and not self.in_hidden:
            self.essential_html += f"</{tag}>"

    def handle_data(self, data):
        if not self.in_footer and not self.in_img and not self.in_script and not self.in_hidden:
            self.essential_html += data


def is_missed(html):
    soup = bs(html, "html.parser")
    plain_text = soup.get_text()
    character_count = len(plain_text)
    return character_count < 100;


def extract_essential_html(html_dom):
    try:
        parser = EssentialHTMLParser()
        parser.feed(html_dom)
        html = parser.essential_html
        if is_missed(html):
            return html_dom
        return html
    except Exception as ex:
        return html_dom


def simplify_html(dom_html):
    soup = bs(dom_html)
    cmp_main = soup.find(id='cmp-main')
    def simplify_tag(tag):
        # Create a new tag with the same name
        simplified_tag = soup.new_tag(tag.name)

        # Copy the 'id' and 'class' attributes if they exist
        if tag.has_attr('id'):
            simplified_tag['id'] = tag['id']
            if tag['id'] == "cmp-main":
                i = 0
        if tag.has_attr('class'):
            simplified_tag['class'] = tag['class']

        # Preserve text content
        if tag.string:
            simplified_tag.string = tag.string
        children = tag.children
        if children:
            for child in tag.children:
                child_text = child.get_text(strip=True)
                child_name = child.name
                if "cookies" in child_text:
                    print(child_text)
                if "p" == child_name:
                    print(child_text)
                if child_name:  # Check if the child is a tag
                    simplified_tag.append(simplify_tag(child))
                else:
                    simplified_tag.append(child)
        else:
            simplified_tag.text = tag.text

        return simplified_tag

    simplified_soup = simplify_tag(soup)
    return simplified_soup.prettify()


def get_html_short(html):
    html_short = simplify_html(html)
    return html_short


def extract_banner_data(driver, banner_item):
    banner_data = {}

    try:
        banner, shadow_host = get_banner_obj(banner_item)
    except Exception as ex:
        driver.switch_to.default_content()
        return

    try:
        banner_data["captured_area"] = calc_area(
            list(banner.size.values())) / calc_area(list(get_win_inner_size(driver)))
        banner_data["x"] = banner.location["x"]
        banner_data["y"] = banner.location["y"]
        banner_data["w"] = banner.size["width"]
        banner_data["h"] = banner.size["height"]
        html = to_html(banner)
        banner_data['html'] = html
        # html_short = get_html_short(html)
        html_short = extract_essential_html(html)
        banner_data['html_short'] = html_short
        banner_data['is_sub'] = is_sub(banner.text, html)
        banner_data['lang'] = detect_lang(banner.text)
        if type(banner_item) is tuple:
            if shadow_host is not None:
                banner_data["shadow_dom"] = True
            else:
                banner_data["iFrame"] = True
                driver.switch_to.default_content()
        else:
            banner_data["iFrame"] = False
            banner_data["shadow_dom"] = False
    except Exception as ex:
        return

    return banner_data


def get_data_dicts(banner_data, visit_id):
    global this_domain, visit_db, banner_db, html_db, this_index
    try:
        # visit_id = this_index
        banner_id = random.getrandbits(53)
        b_row_dict = {'banner_id': banner_id,
                      'visit_id': visit_id, 'domain': this_domain}
        h_row_dict = {'banner_id': banner_id,
                      'visit_id': visit_id, 'domain': this_domain}
        b_row_dict.update(banner_data)
        h_row_dict['html'] = banner_data["html"]
        h_row_dict['html_short'] = banner_data["html_short"]
        del b_row_dict['html']
        del b_row_dict['html_short']

        try:
            banner_db.loc[banner_db.shape[0],
                          b_row_dict.keys()] = b_row_dict.values()
            html_db.loc[html_db.shape[0], h_row_dict.keys()] = h_row_dict.values()
        except:
            pass
    except Exception as ex:
        raise
    finally:
        pass
    
    return b_row_dict, h_row_dict


def take_banners_sc(driver, banners, data):
    global SCREENSHOT
    if SCREENSHOT:
        if banners:
            for j, banner_item in enumerate(banners):
                try:
                    take_banner_sc(driver, banner_item, data, j)
                except Exception as ex:
                    print("Error taking banner screenshot: ", ex)
        elif NOBANNER_SC:
            take_current_page_sc(driver, data, nobanner_sc_dir)


def extract_banners_data(driver, banners):
    banners_data = []
    for banner_item in banners:
        banner_data = extract_banner_data(driver, banner_item)
        if banner_data:
            banners_data.append(banner_data)
    return banners_data


def halt_for_sleep(start_time, time_to_wait):
    if start_time:
        while True:
            cur_time = datetime.now()
            completion_time = cur_time - start_time
            insec = completion_time.total_seconds()
            if insec < time_to_wait:
                time.sleep(0.5)
            else:
                return cur_time



def click_continue_btn(driver, i):
    wait = WebDriverWait(driver, 20)
    continue_btn = wait.until(ec.visibility_of_element_located(
        (By.XPATH, '//*[@id="container"]/div/div[2]/div/div/div[1]/div[2]/div/div/form/div/button')))
    take_current_page_sc(suffix=suffix(5) + "__before" + str(i + 1))
    continue_btn.click()
    time.sleep(0.5)
    body_el = wait.until(ec.visibility_of_element_located(
        (By.TAG_NAME, 'body')))
    time.sleep(0.5)
    take_current_page_sc(suffix=suffix(5) + "_after" + str(i + 1))


def interact_with_banners(driver, data, choice, safari = False):  # choices: 1.accept 2.reject
    global rej_flag, this_banner_lang, this_interact_time, GPT_USED
    try:
        btn_flag = False
        for i, banner in enumerate(data.banners):
            # btn_status: 1. accept 2. reject; btn_set_status: 3. setting 1. add-on, 2, GPT rej clicked, -1 GPT set clicked; for all if neg then it is non-explicit;
            # btn_status = {"btn_status": 0, "btn_set_status": 0, "gpt_usage": 0}
            btn_status = {"btn_status": 0, "btn_set_status": 0}
            if choice:
                print("  Interacting with banner {} of {}".format(i + 1, len(data.banners)))
                interact_with_banner(driver, banner, data.banners_data, choice, btn_status, i, safari=safari)
                print("  Successfully interacted with banner {} of {}".format(i + 1, len(data.banners)))
                data.nc_cmp_name = get_cmp_name_nc(driver)

            if not btn_flag or (abs(data.btn_status["btn_status"]) != choice and abs(btn_status["btn_status"]) == choice) or abs(btn_status["btn_set_status"]) == 1:
                data.btn_status = btn_status
                data.interact_time = time.time() * 1000
                test_time = datetime.now().timestamp() * 1000
                btn_flag = True

            rej_flag = False
            GPT_USED = 0

    except Exception as ex:
        raise


def take_page_sc(driver, data):
    take_current_page_sc(driver, data)


def run_banner_detection(driver, data, safari = False):
    global num_banners, this_start_time
    data.domain = get_current_domain(driver, data.url)
    banners = detect_banners(driver, data, safari= safari)
    print("  Detected {} banners".format(len(banners)))

    # ERROR IN HERE
    take_banners_sc(driver, banners, data)
    
    # num_banners = len(banners)

    return banners



# --- used ---
def run_ONE_pc_AdsCrawler(driver, choice, domain, url, headless = None, dir_bc = None):  # this function is used for run the banner detection module only (Not through OpenWPM)
    global counter
    init_ONE_pc(headless=headless, domain=domain, dir = dir_bc)
    res = None
    try:
        res = run_all_for_domain_AdsCrawler(driver, url, choice)     
        time.sleep(2)
        return res
    except Exception:
        raise
# --- used ---

def run_ONE_pc_nonDB(driver, driver_ref, choice, domain, url, headless = None, dir_bc = None, id_site=None, id_csv=None, country=None, run_no=None):  # this function is used for run the banner detection module only (Not through OpenWPM)
    global counter
    init_ONE_pc(headless=headless, domain=domain, dir = dir_bc)
    res = None
    res = run_all_for_domain_nonDB(driver, driver_ref, domain, url, choice, ID_SITE=id_site, ID_CSV=id_csv, COUNTRY=country, RUN_NO=run_no)

    # driver.delete_all_cookies()
    # driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    time.sleep(2)
    return res

def run_all_for_domain_nonDB(driver, driver_ref, DMN, RAW_URL, CHOICE, ID_SITE=None, ID_CSV=None, COUNTRY=None, RUN_NO=None):
    from urllib.parse import urlparse
    global counter, SLEEP_TIME, this_domain
    
    if ID_SITE is not None:
        after_flag = {"value": False}
        events = []
        stop_event = threading.Event()
        listener = threading.Thread(target=performance_log_listener, args=(driver, events, stop_event, after_flag), daemon=True)

        driver_ref["stop_event"] = stop_event
        driver_ref["listen"] = listener

        listener.start()
        time.sleep(1)
    
    try:
        driver.get(RAW_URL)
    except:
        try:
            driver.execute_script("window.stop();")
        except:
            try:
                driver.execute_cdp_cmd("Page.stopLoading", {})
            except:
                pass

    time.sleep(40)

    URL = driver.current_url
    DMN = urlparse(URL).netloc
    
    this_domain = DMN
    has_banner = None
    try:
        class Data:
            url = URL
            domain = DMN
            choice = CHOICE
            banners = []
            banners_data = []
            CMP = {}
            index = None
            sleep = SLEEP_TIME
            ttw = 0   # time to wait (to show the banner)
            status = None
            btn_status = None
            openwpm = False
            btn_status = {"btn_status": 0, "btn_set_status": 0, "gpt_usage": 0}
            nc_cmp_name = None
            interact_time = None
            goal = "something"
            start_time = datetime.now()
            finish_time = 0


        # print(visit_db.shape)
        # print(visit_db.empty)
        # print(visit_db.head())
        
        Data.index = visit_db.shape[0]
        Data.visit_id = visit_db.shape[0]
        if BANNERCLICK:
            #print("Running banner detection for domain: ", DMN)
            banners = run_banner_detection(driver, Data)
            #print("Banners detected: ", len(banners))
            take_page_sc(driver, Data)
            Data.banners = banners
            Data.banners_data = extract_banners_data(driver, banners)
            if banners:
                has_banner = True

        #if CMPDETECTION:
        #    Data.CMP = cd.run_cmp_detection(driver)

        if CHOICE == 0 or has_banner:
            #GET COOKIES BEFORE INTERACTION
            time.sleep(2)
            print("Getting cookies and network data before interaction for domain: ", DMN)

            try:
                origin = driver.execute_script("return location.origin")
            except Exception as e:
                print(str(e))
                raise

            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {})
            local_storage = getLocalStorage(driver)
            session_storage = getSessionStorage(driver)
            curr_url = driver.current_url

            with get_db_conn() as conn:
                save_cookies_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, cookies=cookies, current_url=curr_url, origin=origin, after=False)
                save_local_storage_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, local_storage=local_storage, current_url=curr_url, origin=origin, after=False)
                save_session_storage_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, session_storage=session_storage, current_url=curr_url, origin=origin, after=False)
            
            print("Saved cookies data before interaction for domain: ", DMN)
            time.sleep(3)
        
        after_flag["value"] = True

        if BANNERINTERACTION and has_banner:
            print("Running banner interaction for domain: ", DMN)
            interact_with_banners(driver, Data, CHOICE)

        if SLEEP_AFTER_INTERACTION:
            print("Sleeping after interaction for domain: ", DMN)
            Data.start_time = datetime.now()

        if CHOICE==0 or has_banner:
            start_counter = time.monotonic()
            print("Scrolling...")
            if is_infinite_scroll_page(driver):
                print("[INFO] Page detected as INFINITE SCROLL.")
                scroll_infinite(driver,lite_mode=False,step=800, pause=0.5)
            else:
                print("[INFO] Page is NORMAL scroll.")
                slow_scroll_page(driver,lite_mode=False, step=800, pause=0.5)

            smart_delay(start_counter, min_interval=30)
            
            #GET COOKIES AFTER INTERACTION
            print("Getting cookies and network data after interaction for domain: ", DMN)

            try:
                driver.execute_script("window.stop();")
            except:
                try:
                    driver.execute_cdp_cmd("Page.stopLoading", {})
                except:
                    pass

            stop_event.set()
            listener.join(timeout=3)

            try:
                origin = driver.execute_script("return location.origin")
            except Exception as e:
                print(str(e))
                raise

            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {})
            local_storage = getLocalStorage(driver)
            session_storage = getSessionStorage(driver)
            curr_url = driver.current_url
            
            with get_db_conn() as conn:
                try:
                    save_cookies_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, cookies=cookies, current_url=curr_url, origin=origin, after=True)
                    save_local_storage_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, local_storage=local_storage, current_url=curr_url, origin=origin, after=True)
                    save_session_storage_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, session_storage=session_storage, current_url=curr_url, origin=origin, after=True)
                except Exception as e:
                    print("Err:",e)
            print("Saved cookies data after interaction for domain: ", DMN)
            print(f"[INFO] Collected {len(events)} network events after")
            with get_db_conn() as conn:
                try:
                    save_full_network_data_AdsLanding(conn, driver, ID_SITE, ID_CSV, COUNTRY, RUN_NO, CHOICE, URL, events)
                except Exception as e:
                    print("Err: ",e)
                #save_network_AdsLanding_data(conn, ID_SITE, URL, events, after=True)
            print("Saved network data after interaction for domain: ", DMN)
            time.sleep(1)


            events = []
            stop_event = threading.Event()
            listener = threading.Thread(target=performance_log_listener, args=(driver, events, stop_event, after_flag), daemon=True)
            listener.start()
            time.sleep(1)
    
            try:
                driver.get(URL)
            except:
                try:
                    driver.execute_script("window.stop();")
                except:
                    try:
                        driver.execute_cdp_cmd("Page.stopLoading", {})
                    except:
                        pass

            time.sleep(2)

            start_counter = time.monotonic()
            print("Scrolling...")
            if is_infinite_scroll_page(driver):
                print("[INFO] Page detected as INFINITE SCROLL.")
                scroll_infinite(driver,lite_mode=False, step=800, pause=0.5)   # Hàm scroll dành riêng cho trang vô tận
            else:
                print("[INFO] Page is NORMAL scroll.")
                slow_scroll_page(driver,lite_mode=False, step=800, pause=0.5)  # Hàm scroll hiện tại của bạn

            smart_delay(start_counter, min_interval=30)
            #GET COOKIES AFTER INTERACTION
            print("Getting cookies and network data after interaction for domain: ", DMN)

            try:
                driver.execute_script("window.stop();")
            except:
                try:
                    driver.execute_cdp_cmd("Page.stopLoading", {})
                except:
                    pass

            stop_event.set()
            listener.join(timeout=3)
            try:
                origin = driver.execute_script("return location.origin")
            except Exception as e:
                print(str(e))
                raise
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {})
            local_storage = getLocalStorage(driver)
            session_storage = getSessionStorage(driver)
            curr_url = driver.current_url

            with get_db_conn() as conn:
                try:
                    save_cookies_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE ,this_domain=DMN, cookies=cookies, current_url=curr_url, origin=origin, after=True)
                    save_local_storage_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, local_storage=local_storage, current_url=curr_url, origin=origin, after=True)
                    save_session_storage_pg(conn, id_site=ID_SITE, id_csv=ID_CSV, country=COUNTRY, run_no=RUN_NO, choice=CHOICE, this_domain=DMN, session_storage=session_storage, current_url=curr_url, origin=origin, after=True)
                except Exception as e:
                    print("Err:",e)
            print("Saved cookies data after interaction for domain: ", DMN)
            print(f"[INFO] Collected {len(events)} network events after")
            with get_db_conn() as conn:
                try:
                    save_full_network_data_AdsLanding(conn, driver, ID_SITE, ID_CSV, COUNTRY, RUN_NO, CHOICE, URL, events, after=True)
                except Exception as e:
                    print("Err: ",e)
                    traceback.print_exc()
            print("Saved network data after interaction for domain: ", DMN)
            time.sleep(1)

        else:
            stop_event.set()
            listener.join(timeout=3)
        

        if ID_SITE is not None:
            domain_url = this_domain
            cmp_name = Data.nc_cmp_name if Data.nc_cmp_name else "unknown"
            user_choice = "accept" if CHOICE == 1 else "reject" if CHOICE == 2 else "not interacted"
            data_ = Data.banners_data
            html_ = None

            for banner_data in data_:
                html_ = banner_data["html"]
            
            if has_banner:
                try:
                    with get_db_conn() as conn:
                        insert_consent_banner(conn, ID_SITE, ID_CSV, COUNTRY, RUN_NO, domain_url, cmp_name, user_choice, html_, more_information="")
                except Exception as ex:
                    print("Error inserting into database: ", ex)

        data_ = Data.banners_data
        html_ = None

        for banner_data in data_:
            html_ = banner_data["html"]

        halt_for_sleep(Data.start_time, 10)
        

    except Exception as ex:
        raise
    
   
    return has_banner

def run_all_for_domain_AdsCrawler(driver, raw_url, CHOICE):
    from urllib.parse import urlparse
    
    global counter, SLEEP_TIME, this_domain
    
    driver.get(raw_url)
    time.sleep(5)

    URL = driver.current_url
    DMN = urlparse(URL).netloc
    
    
    this_domain = DMN
    has_banner = None
    try:
        class Data:
            url = URL
            domain = DMN
            choice = CHOICE
            banners = []
            banners_data = []
            CMP = {}
            index = None
            sleep = SLEEP_TIME
            ttw = 0   # time to wait (to show the banner)
            status = None
            btn_status = None
            openwpm = False
            btn_status = {"btn_status": 0, "btn_set_status": 0, "gpt_usage": 0}
            nc_cmp_name = None
            interact_time = None
            goal = "something"
            start_time = datetime.now()
            finish_time = 0


        # print(visit_db.shape)
        # print(visit_db.empty)
        # print(visit_db.head())
        
        Data.index = visit_db.shape[0]
        Data.visit_id = visit_db.shape[0]
        if BANNERCLICK:
            #print("Running banner detection for domain: ", DMN)
            banners = run_banner_detection(driver, Data)
            #print("Banners detected: ", len(banners))
            take_page_sc(driver, Data)
            Data.banners = banners
            Data.banners_data = extract_banners_data(driver, banners)
            if banners:
                has_banner = True
            #print(has_banner)
        #if CMPDETECTION:
        #    Data.CMP = cd.run_cmp_detection(driver)

        
        if BANNERINTERACTION and has_banner:
            print("Running banner interaction for domain: ", DMN)
            interact_with_banners(driver, Data, CHOICE)

        if SLEEP_AFTER_INTERACTION:
            print("Sleeping after interaction for domain: ", DMN)
            Data.start_time = datetime.now()

        

        data_ = Data.banners_data
        html_ = None

        for banner_data in data_:
            html_ = banner_data["html"]

        halt_for_sleep(Data.start_time, 10)
        

    except Exception as ex:
        raise
    
   
    return has_banner
    
