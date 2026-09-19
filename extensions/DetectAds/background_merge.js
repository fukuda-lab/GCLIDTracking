/* ============================
   MERGED RULE FILE (LOCAL)
   ============================ */
const MERGED_RULE_FILE = "rules/merged_rules.json";

/* ============================
   STORAGE IN MEMORY
   ============================ */
let BLOCK_RULES = [];
let ALLOW_RULES = [];
let NETWORK_DOMAINS_SET = new Set();

/* ============================
   LOAD LOCAL MERGED RULE JSON
   ============================ */
async function loadMergedRules() {
  try {
    const url = chrome.runtime.getURL(MERGED_RULE_FILE);
    const resp = await fetch(url);
    const data = await resp.json();

    BLOCK_RULES = data.block || [];
    ALLOW_RULES = data.allow || [];

    const networkDomains = (data.networkDomains || [])
      .map(d => d.trim().toLowerCase())
      .filter(Boolean);

    NETWORK_DOMAINS_SET = new Set(networkDomains);

    console.log(
      `[AdblockDB] Loaded merged rules → block: ${BLOCK_RULES.length}, allow: ${ALLOW_RULES.length}, network: ${NETWORK_DOMAINS_SET.size}`
    );

  } catch (e) {
    console.error("[AdblockDB] Failed to load merged_rules.json:", e);
  }
}

loadMergedRules
/* ============================
   INITIALIZE ON INSTALL + STARTUP
   ============================ */


//chrome.runtime.onInstalled.addListener(loadMergedRules);
//chrome.runtime.onStartup.addListener(loadMergedRules);

/* ============================
   CONTENT SCRIPT REQUEST → RULES
   ============================ */
chrome.runtime.onMessage.addListener((msg, sender, send) => {
  if (msg === "getAllRules") {
    if (BLOCK_RULES.length === 0 && ALLOW_RULES.length === 0) {
      loadMergedRules().then(() => {
        send({ blocked: BLOCK_RULES, allowed: ALLOW_RULES });
      });
      return true; // giữ channel mở
    }
    //console.log(BLOCK_RULES.length)
    send({ blocked: BLOCK_RULES, allowed: ALLOW_RULES });
    return true;
  }
});

/* ============================
   SAFE SEND MESSAGE TO TAB
   ============================ */
function safeSendMessage(tabId, payload) {
  if (!tabId || tabId < 0) return;

  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError || !tab) return;

    chrome.tabs.sendMessage(tabId, payload, () => {
      if (chrome.runtime.lastError) {
        if (!chrome.runtime.lastError.message.includes("Receiving end does not exist")) {
          console.warn("[AdblockDB] sendMessage error:", chrome.runtime.lastError.message);
        }
      }
    });
  });
}



/* ============================
   NETWORK LISTENER (webRequest)
   ============================ */
   
/*
chrome.webRequest.onBeforeRequest.addListener(
  function (details) {
    try {
      if (!details.tabId || details.tabId < 0) return;

      const url = new URL(details.url);
      const host = url.hostname.toLowerCase();
      const tail2 = host.split(".").slice(-2).join(".");

      if (NETWORK_DOMAINS_SET.has(host) || NETWORK_DOMAINS_SET.has(tail2)) {
        safeSendMessage(details.tabId, {
          type: "net-hit",
          host,
          url: details.url
        });
      }

    } catch (e) {
      // ignore
    }
  },
  { urls: ["<all_urls>"] }
);
*/

/* ============================
   OUTBOUND AD CLICK CAPTURE
   ============================ */
/*
chrome.webRequest.onBeforeRequest.addListener(
  function (details) {
    try {
      // ignore non-tab request (service workers, extensions)
      if (details.tabId < 0) return;

      const url = new URL(details.url);
      const host = url.hostname.toLowerCase();

      // đây là domain thường gặp của Google Ads, Facebook Ads
      const AD_CLICK_DOMAINS = [
        "doubleclick.net",
        "googlesyndication.com",
        "googleadservices.com",
        "adservice.google.com",
        "facebook.com",
        "tpc.googlesyndication.com",
        "g.doubleclick.net",
        "adclick.g.doubleclick.net"
      ];

      const isAdClick = AD_CLICK_DOMAINS.some(d => host.includes(d));

      if (isAdClick) {
        safeSendMessage(details.tabId, {
          type: "ad-outbound",
          url: details.url,
          host
        });
      }

    } catch (e) {
      console.warn("[AdblockDB] outbound error:", e);
    }
  },
  { urls: ["<all_urls>"] }
);
*/