#!/usr/bin/env python3
import base64, json, socket, urllib.parse, time, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- STRICT TARGETS (Physical IP Verification) ---
TARGET_CODES = {"CA", "US", "GB", "UK"}

# Tuning for GitHub Actions
FETCH_WORKERS = 50
TEST_WORKERS = 100  
TIMEOUT_FETCH = 15
TIMEOUT_TCP = 2.5   # Fast nodes only
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
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vless.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vmess.txt",
    "https://raw.githubusercontent.com/LonUp/NodeList/main/V2RAY/Latest.txt"
]

def get_links(url):
    try:
        r = requests.get(url, timeout=TIMEOUT_FETCH)
        content = r.text
        if not any(x in content[:100] for x in ['vmess://', 'vless://']):
            try:
                content = base64.b64decode(content.strip() + "==").decode('utf-8', 'ignore')
            except: pass
        return re.findall(r'(vless|vmess)://[^\s]+', content)
    except: return []

def parse(link):
    try:
        if link.startswith("vmess://"):
            d = json.loads(base64.b64decode(link[8:] + "==").decode('utf-8'))
            return {"h": d.get("add"), "p": int(d.get("port")), "raw": link}
        parsed = urllib.parse.urlparse(link)
        return {"h": parsed.hostname, "p": parsed.port or 443, "raw": link}
    except: return None

def check_tcp(node):
    try:
        with socket.create_connection((node['h'], node['p']), timeout=TIMEOUT_TCP):
            return node
    except: return None

def verify_geo_and_filter(nodes):
    """The Ultimate Filter: Checks physical location of every working node."""
    if not nodes: return []
    unique_hosts = list({n['h'] for n in nodes})
    mapping = {}
    
    print(f"[*] Analyzing {len(unique_hosts)} IP locations...")
    for i in range(0, len(unique_hosts), 100):
        batch = unique_hosts[i:i+100]
        try:
            r = requests.post("http://ip-api.com/batch?fields=query,countryCode", json=batch, timeout=15)
            for res in r.json():
                if 'query' in res: mapping[res['query']] = res.get('countryCode')
        except: pass
        time.sleep(0.6) # Anti-ban delay
    
    verified = []
    for n in nodes:
        code = mapping.get(n['h'])
        if code in TARGET_CODES:
            n['cc'] = code
            verified.append(n)
    return verified

def main():
    start_time = time.time()
    
    # 1. Scrape everything
    print("[*] Deep Scouring GitHub Repositories...")
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        link_lists = list(pool.map(get_links, SUBSCRIPTION_URLS))
    
    all_raw = list(set([item for sublist in link_lists for item in sublist]))[:MAX_LINKS]
    print(f"[*] Found {len(all_raw)} total unique links.")

    # 2. Parse all (No filtering yet)
    nodes = []
    for link in all_raw:
        p = parse(link)
        if p: nodes.append(p)

    # 3. Test Connectivity (The primary filter)
    print(f"[*] Testing {len(nodes)} nodes for connectivity...")
    working = []
    with ThreadPoolExecutor(max_workers=TEST_WORKERS) as pool:
        futures = [pool.submit(check_tcp, n) for n in nodes]
        for f in as_completed(futures):
            res = f.result()
            if res: working.append(res)
    
    print(f"[*] {len(working)} nodes are alive and fast.")

    # 4. Filter by physical location (Geo-Lock)
    print("[*] Applying Strict CA/US/UK Geo-Lock...")
    final_nodes = verify_geo_and_filter(working)
    
    # 5. Sort CA -> US -> UK
    order = {"CA": 0, "US": 1, "GB": 2, "UK": 2}
    final_nodes.sort(key=lambda x: order.get(x['cc'], 9))
    
    # Deduplicate and save
    seen, output = set(), []
    for n in final_nodes:
        key = f"{n['h']}:{n['p']}"
        if key not in seen:
            seen.add(key)
            output.append(n['raw'])
            
    if output:
        Path("hiddify_ca_us_uk.txt").write_text("\n".join(output))
        print(f"\n[DONE] Saved {len(output)} strictly verified CA/US/UK nodes in {time.time()-start_time:.1f}s")
    else:
        print("\n[-] No CA/US/UK nodes found. This can happen if the free pools are currently empty for these regions.")

if __name__ == "__main__":
    main()
