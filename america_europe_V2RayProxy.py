#!/usr/bin/env python3
import base64, json, socket, urllib.parse, time, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure requests is available
try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- CONFIGURATION ---
TARGET_CODES = {"CA", "US", "GB", "UK"}
FETCH_WORKERS = 50
TEST_WORKERS = 80
TIMEOUT_FETCH = 20
TIMEOUT_TCP = 3.5   # Increased for better reliability
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
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/all_configs.txt",
    "https://raw.githubusercontent.com/LonUp/NodeList/main/V2RAY/Latest.txt"
]

def get_links(url):
    try:
        r = requests.get(url, timeout=TIMEOUT_FETCH)
        content = r.text
        # Logic to handle base64 wrapped subs
        if not any(x in content[:200] for x in ['vmess://', 'vless://']):
            try:
                content = base64.b64decode(content.strip() + "==").decode('utf-8', 'ignore')
            except: pass
        return re.findall(r'(vless|vmess)://[^\s]+', content)
    except: return []

def parse(link):
    try:
        if link.startswith("vmess://"):
            # VMess is complex; we extract the host for GeoIP
            d = json.loads(base64.b64decode(link[8:] + "==").decode('utf-8'))
            return {"h": d.get("add"), "p": int(d.get("port")), "raw": link}
        parsed = urllib.parse.urlparse(link)
        if parsed.hostname:
            return {"h": parsed.hostname, "p": parsed.port or 443, "raw": link}
    except: return None

def check_tcp(node):
    try:
        with socket.create_connection((node['h'], node['p']), timeout=TIMEOUT_TCP):
            return node
    except: return None

def verify_geo(nodes):
    if not nodes: return []
    unique_hosts = list({n['h'] for n in nodes})
    mapping = {}
    for i in range(0, len(unique_hosts), 100):
        batch = unique_hosts[i:i+100]
        try:
            r = requests.post("http://ip-api.com/batch?fields=query,countryCode", json=batch, timeout=15)
            for res in r.json():
                if 'query' in res: mapping[res['query']] = res.get('countryCode')
        except: pass
        time.sleep(0.8)
    
    verified = []
    for n in nodes:
        code = mapping.get(n['h'])
        if code in TARGET_CODES:
            n['cc'] = code
            verified.append(n)
    return verified

def main():
    start_time = time.time()
    out_file = Path("hiddify_ca_us_uk.txt")
    
    # GUARANTEE: Create file immediately so Git doesn't crash
    out_file.write_text("")

    print("[*] Phase 1: Scraping deep GitHub repositories...")
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        link_lists = list(pool.map(get_links, SUBSCRIPTION_URLS))
    
    all_raw = list(set([item for sublist in link_lists for item in sublist]))[:MAX_LINKS]
    print(f"[*] Total links found: {len(all_raw)}")

    print("[*] Phase 2: Testing connectivity...")
    working = []
    parsed_nodes = []
    for link in all_raw:
        p = parse(link)
        if p: parsed_nodes.append(p)

    with ThreadPoolExecutor(max_workers=TEST_WORKERS) as pool:
        futures = [pool.submit(check_tcp, n) for n in parsed_nodes]
        for f in as_completed(futures):
            res = f.result()
            if res: working.append(res)
    
    print(f"[*] Online nodes: {len(working)}")

    print("[*] Phase 3: Geo-Locking (CA/US/UK Only)...")
    final_nodes = verify_geo(working)
    
    # Deduplicate and finalize
    order = {"CA": 0, "US": 1, "GB": 2, "UK": 2}
    final_nodes.sort(key=lambda x: order.get(x['cc'], 9))
    
    seen, output = set(), []
    for n in final_nodes:
        key = f"{n['h']}:{n['p']}"
        if key not in seen:
            seen.add(key)
            output.append(n['raw'])
            
    if output:
        out_file.write_text("\n".join(output))
        print(f"\n[DONE] Saved {len(output)} nodes. Total time: {time.time()-start_time:.1f}s")
    else:
        print("\n[!] No nodes found in CA/US/UK during this run.")

if __name__ == "__main__":
    main()
