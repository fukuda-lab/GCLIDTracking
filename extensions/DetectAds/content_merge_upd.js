const ENABLE_SELECTOR = true;
const ENABLE_NETWORK = false;
const ENABLE_HEURISTIC = false;
const NETWORK_SCAN_INTERVAL = 8000; // ms

(async function () {

let blocked = [];
let allowed = [];

// ---------- LOAD RULES FROM BACKGROUND (merged JSON) -------------
if (ENABLE_SELECTOR) {
  try {
    const data = await chrome.runtime.sendMessage("getAllRules");
    blocked = data.blocked || [];
    allowed = data.allowed || [];
    console.log(`[Adblock Marker] Loaded ${blocked.length} blocked rules + ${allowed.length} allowed rules`);
    } catch (e) {
      console.error("[Adblock Marker] Failed to load rules:", e);
    }
}

// ---------- PRE-PARSE COSMETIC SELECTORS ----------
const blockedCss = blocked
  .filter(r => r.startsWith("##"))
  .map(r => r.replace(/^##/, "").replace(/\\"/g, '"').trim()); // bỏ escape \"  

const allowedCss = allowed
  .filter(r => r.startsWith("@@##"))
  .map(r => r.replace(/^@@##/, "").replace(/\\"/g, '"').trim());



// const blockedCss = blocked
// .filter(r => r.startsWith("##"))
// .map(r => r.replace(/^##/, "").trim());

// // Acceptable Ads → convert @@## → block-style red highlight
// const allowedCss = allowed
// .filter(r => r.startsWith("@@##"))
// .map(r => r.replace(/^@@##/, "").trim());

console.log(`[Adblock Marker] Cosmetic selectors:`,
blockedCss.length, "blocked,", allowedCss.length, "allowed");

const marked = new WeakMap();
const urlMeta = new WeakMap();

function addURLMeta(el, source, url) {
  if (!el) return;

  // WeakMap internal
  if (!urlMeta.has(el)) urlMeta.set(el, []);
  urlMeta.get(el).push({ source, url});

  const old = el.getAttribute("data-ad-urls");
  const list = old ? JSON.parse(old) : [];
  list.push({source, url});
  el.setAttribute("data-ad-urls", JSON.stringify(list));
  
  // if (!urlMeta.has(el)) {
  //   urlMeta.set(el, []);
  // }
  // urlMeta.get(el).push({ source, url });
}

//const marked = new WeakSet();

// ---------- MARKER UI ----------
function setLabel(el, color, label) {
  const tag = document.createElement("div");
  tag.textContent = label;
  Object.assign(tag.style, {
    position: "absolute",
    top: "0",
    left: "0",
    background: color,
    color: (color === "red" ? "white" : "black"),
    fontSize: "10px",
    fontWeight: "bold",
    padding: "1px 3px",
    zIndex: 999999,
    pointerEvents: "none",
    borderRadius: "0 0 3px 0"
  });
  el.prepend(tag);
}

function highlight(el, color, cls, label, priority, extraUrl) {
   // priority: 1 = selector, 2 = network, 3 = heuristic

  const cur = marked.get(el);
  if (cur && cur <= priority) return;
  //if (!el || marked.has(el)) return;
  marked.set(el, priority);
  //marked.add(el);

  if (extraUrl) {
    addURLMeta(el, label, extraUrl);
  }

  const direct = el.src || el.href || el.getAttribute("data-src") || el.srcset;
  if (direct) {
    addURLMeta(el, "direct", direct);
  }

  el.classList.add(cls);
  el.style.outline = `2px solid ${color}`;
  el.style.backgroundColor =
    color === "red" ? "rgba(255,0,0,0.07)"
    : color === "limegreen" ? "rgba(0,255,0,0.07)"
    : "rgba(255,165,0,0.07)";

  setLabel(el, color, label);

  // console.log("=== [Ad Marked] ===========================");
  // console.log("Type:", label);
  // console.log("Element:", el);
  // console.log("URLs:");
  // console.table(urlMeta.get(el));
  // console.log("==========================================");



}

// ---------- APPLY SELECTOR FILTERS ----------
function applySelectorsTo(root) {
if (!ENABLE_SELECTOR) return;


// Block rules
for (const sel of blockedCss) {
  try {
    root.querySelectorAll(sel)
      .forEach(el => highlight(el, "red", "adblocked-marker", "ADS",1, sel));
  } catch { }
}

// Acceptable Ads → cũng highlight đỏ
for (const sel of allowedCss) {
  try {
    root.querySelectorAll(sel)
      .forEach(el => highlight(el, "red", "adblocked-acceptablead-marker", "ADS",1,sel));
  } catch { }
}


}

applySelectorsTo(document);

// ---------- SPECIAL AD DETECTION (NEW MODULE) ----------
function detectSpecialAdSlots(root = document) {
  const selectors = [
    //'iframe[title="3rd party ad content"]',
    'iframe[id^="google_ads_iframe"]',
    '[data-testid="StandardAd"]',
    '[id^="dfp-ad-"]',
    '.dfp-ad-wrapper',
    '.dfp-ad-slot',
    '.ad-slot',
    '.ad-wrapper',
    '.google-ad',
    // Thêm Admicro / Kenh14
    '.khw-adk14-wrapper',
    '#admzone49',
    //'script[src*="admicro.vn"]',
    //'script.adnetwork-marker'
  ];


  selectors.forEach(sel => {
  try {
    root.querySelectorAll(sel).forEach(el => {
      highlight(el, "red", "ad-special-marker", "AD");
    });
  } catch {}
  });
}

//detectSpecialAdSlots();

// ---------- WATCH FOR DOM CHANGES ----------
const observer = new MutationObserver(muts => {
  for (const m of muts) {
    for (const node of m.addedNodes) {
      if (node.nodeType === 1) {
        applySelectorsTo(node);
        //detectSpecialAdSlots(node);
      }
    }
  }
});

observer.observe(document.documentElement, {
  childList: true,
  subtree: true
});

// ---------- NETWORK HEURISTIC ----------
const netPatterns =
/(doubleclick|googlesyndication|adservice|taboola|outbrain|quantserve|adnxs|criteo|adsafeprotected|advertising|revcontent|scorecardresearch|analytics|tracker)/i;

function scanNetworkRequests() {
  if (!ENABLE_NETWORK) return;


  const entries = performance.getEntriesByType("resource");
  for (const e of entries) {
    if (netPatterns.test(e.name)) {
      try {
        const url = new URL(e.name, location.href);
        const host = url.hostname.toLowerCase();

        const tags = ["iframe", "img", "script", "video"];
        tags.forEach(tag => {
          document.querySelectorAll(tag).forEach(el => {
            const attr = el.src || el.srcset || el.getAttribute("data-src") || "";
            if (!attr) return;
            try {
              const u = new URL(attr, location.href);
              const h = u.hostname.toLowerCase();
              if (h === host || h.endsWith(`.${host}`)) {
                highlight(el, "red", "adnetwork-marker", "AD NETWORK",2);
              }
            } catch {}
          });
        });
      } catch {}
    }
  }
  //detectSpecialAdSlots();
}

function watchNetworkIdle() {
  if (!ENABLE_NETWORK) return;
  let lastCount = 0;
  setInterval(() => {
  const nowCount = performance.getEntriesByType("resource").length;
  if (nowCount === lastCount) scanNetworkRequests();
  lastCount = nowCount;
  }, NETWORK_SCAN_INTERVAL);
}

watchNetworkIdle();

// ---------- NETWORK EVENTS (rule-based) ----------

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "net-hit") {
    const host = msg.host.toLowerCase();

    ["iframe","img","script","video","a"].forEach(tag => {
      document.querySelectorAll(tag).forEach(el => {
        const attr = el.src || el.srcset || el.getAttribute("data-src") || el.getAttribute("href") || "";
        if (!attr) return;
        try {
          const u = new URL(attr, location.href);
          const h = u.hostname.toLowerCase();
          if (h === host || h.endsWith(`.${host}`)) {
            highlight(el, "red", "adnetwork-marker", "AD NETWORK",2);
          }
        } catch {}
      });
    });
  }
});


chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "ad-outbound"){
    const outUrl = msg.url;
    const outHost = msg.host;

    console.log("URL received: ", outUrl);

    const adElems = document.querySelectorAll(".adblocked-marker, .adblocked-acceptablead-marker, .possiblead-marker, .adnetwork-marker, .ad-special-marker");
    adElems.forEach(el => {
      const src = el.src || el.getAttribute("src") || el.getAttribute("data-src") || el.href || "";
      if (!src) return;

      try{
        const h = (new URL(src, location.href)).hostname.toLowerCase();

        // Heuristic match host
        const match = h === outHost || h.endsWith("." + outHost) || outHost.endsWith("." + h) || src.includes(outHost);

        if (match){
          console.log("[Ad Marker] → OUTBOUND matched to existing element:", el);
          addURLMeta(el, "outbound", outUrl);
        }

      } catch(e){}
    });
  }
});


// chrome.runtime.onMessage.addListener((msg) => {
// if (msg.type === "net-hit") {
// const host = msg.host.toLowerCase();


//   const tags = ["iframe", "img", "script", "video"];
//   tags.forEach(tag => {
//     document.querySelectorAll(tag).forEach(el => {
//       const attr = el.src || el.srcset || el.getAttribute("data-src") || el.getAttribute("href") || "";
//       if (!attr) return;
//       try {
//         const u = new URL(attr, location.href);
//         const h = u.hostname.toLowerCase();
//         if (h === host || h.endsWith(`.${host}`)) {
//           highlight(el, "red", "adnetwork-marker", "AD NETWORK");
//         }
//       } catch {}
//     });
//   });

//   //detectSpecialAdSlots();
// }


// });

})();
