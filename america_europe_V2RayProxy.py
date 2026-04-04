#!/usr/bin/env python3
import base64, json, socket, urllib.parse, time, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Try to import requests, install if missing (for local testing)
try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- CONFIGURATION (CA, US, UK ONLY) ---
TARGET_CODES = {"CA", "US", "GB", "UK"}
# Keywords & Emojis for instant pre-filtering
RE_TARGET = re.compile(r"CA|CANADA|US|USA|AMERICA|UNITED STATES|UK|GB|LONDON|UNITED KINGDOM|TORONTO|🇨🇦|🇺🇸|🇬🇧", re.I)

# Performance Tuning
FETCH_WORKERS = 50
TEST_WORKERS = 100  # Extreme concurrency
TIMEOUT_FETCH = 10
TIMEOUT_TCP = 2.0   # If a node is slower than 2s, it's not worth keeping
MAX_LINKS = 100000

SUBSCRIPTION_URLS = [
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vless",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vmess",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription1",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription2",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription3",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/ts-sf/fly/main/v2",
    "https://raw.githubusercontent.com/Alireza-ok/xray/main/mix",
    "https://raw.githubusercontent.com/freev2rayconfig/V2RAY_SUBSCRIPTION_LINK/main/v2rayconfigs.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/Leon406/Sub/master/sub/share/vless",
    "https://raw.githubusercontent.com/Leon406/Sub/master/sub/share/vmess",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/all_configs.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/sakha1370/OpenRay/refs/heads/main/output/all_valid_proxies.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vless.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vmess.txt"
]

def get_links(url):
    try:
        r = requests.get(url, timeout=TIMEOUT_FETCH)
        content = r.text
        if not content.startswith(('vmess', 'vless')):
            try: content = base64.b64decode(content + "==").decode('utf-8', 'ignore')
            except: pass
        return re.findall(r'(vless|vmess)://[^\s]+', content)
    except: return []

def parse(link):
    try:
        if link.startswith("vmess://"):
            d = json.loads(base64.b64decode(link[8:] + "==").decode('utf-8'))
            return {"h": d.get("add"), "p": int(d.get("port")), "ps": d.get("ps", ""), "raw": link}
        parsed = urllib.parse.urlparse(link)
        return {"h": parsed.hostname, "p": parsed.port or 443, "ps": parsed.fragment, "raw": link}
    except: return None

def check_tcp(node):
    try:
        with socket.create_connection((node['h'], node['p']), timeout=TIMEOUT_TCP):
            return node
    except: return None

def verify_geo(nodes):
    """The Secret Sauce: Batch check 100 IPs at once."""
    if not nodes: return []
    unique_hosts = list({n['h'] for n in nodes})
    mapping = {}
    for i in range(0, len(unique_hosts), 100):
        batch = unique_hosts[i:i+100]
        try:
            r = requests.post("http://ip-api.com/batch?fields=query,countryCode", json=batch, timeout=10)
            for res in r.json(): mapping[res['query']] = res.get('countryCode')
        except: pass
        time.sleep(0.5) # Minimal sleep to stay under batch limit
    
    verified = []
    for n in nodes:
        code = mapping.get(n['h'])
        if code in TARGET_CODES:
            n['cc'] = code
            verified.append(n)
    return verified

def main():
    start = time.time()
    
    # 1. Parallel Fetch
    print("[*] Rapidly Scouring GitHub...")
    with ThreadPoolExecutor(MAX_WORKERS=FETCH_WORKERS) as pool:
        results = list(pool.map(get_links, SUBSCRIPTION_URLS))
    all_raw = list(set([item for sublist in results for item in sublist]))[:MAX_LINKS]
    
    # 2. Fast Filter & Parse
    print(f"[*] Pre-filtering {len(all_raw)} links...")
    candidates = []
    for link in all_raw:
        if RE_TARGET.search(link): # Fast regex check on raw string
            p = parse(link)
            if p: candidates.append(p)
    
    # 3. Parallel TCP Check
    print(f"[*] Testing {len(candidates)} nodes...")
    working = []
    with ThreadPoolExecutor(MAX_WORKERS=TEST_WORKERS) as pool:
        futures = [pool.submit(check_tcp, c) for c in candidates]
        for f in as_completed(futures):
            res = f.result()
            if res: working.append(res)
    
    # 4. Strict Batch Geo-Verification
    print(f"[*] Verified Online: {len(working)}. Performing final Geo-Lock...")
    final = verify_geo(working)
    
    # 5. Sort CA -> US -> UK
    order = {"CA": 0, "US": 1, "GB": 2, "UK": 2}
    final.sort(key=lambda x: order.get(x['cc'], 9))
    
    # Save (Deduplicate by Host:Port)
    seen, output = set(), []
    for n in final:
        key = f"{n['h']}:{n['p']}"
        if key not in seen:
            seen.add(key)
            output.append(n['raw'])
            
    Path("hiddify_ca_us_uk.txt").write_text("\n".join(output))
    
    elapsed = time.time() - start
    print(f"\n[DONE] Saved {len(output)} verified nodes in {elapsed:.1f} seconds!")

if __name__ == "__main__":
    main()
