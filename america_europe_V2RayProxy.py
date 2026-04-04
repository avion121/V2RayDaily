#!/usr/bin/env python3
import base64, json, os, socket, subprocess, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# --- AUTO INSTALL REQUESTS ---
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- CONFIGURATION ---
MAX_LINKS_TO_PROCESS = 40000 
MAX_VERIFIED_NODES = 100  
GEOIP_RATE_LIMIT = 1.35 
TCP_TIMEOUT = 5
OUTPUT_FILE = "hiddify_ca_us_uk.txt"

# Ensure the output file exists immediately to prevent Git errors
Path(OUTPUT_FILE).touch()

SUBSCRIPTION_URLS = [
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vless",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vmess",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription1",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription2",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/ts-sf/fly/main/v2",
    "https://raw.githubusercontent.com/Alireza-ok/xray/main/mix",
    "https://raw.githubusercontent.com/freev2rayconfig/V2RAY_SUBSCRIPTION_LINK/main/v2rayconfigs.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt"
]

STRICT_ALLOWED_COUNTRIES = {"CA", "US", "GB", "UK"}

def fetch_url(url):
    try:
        r = requests.get(url, timeout=20)
        return r.text if r.status_code == 200 else None
    except: return None

def decode_sub(raw):
    links = []
    if not raw: return []
    for chunk in raw.split():
        try:
            decoded = base64.b64decode(chunk + "==").decode("utf-8", errors="ignore")
            for line in decoded.splitlines():
                if line.startswith(("vmess://", "vless://")): links.append(line.strip())
        except: pass
    for line in raw.splitlines():
        if line.startswith(("vmess://", "vless://")): links.append(line.strip())
    return list(set(links))

def parse_link(link):
    try:
        if link.startswith("vmess://"):
            data = json.loads(base64.b64decode(link[8:] + "==").decode("utf-8"))
            return {"host": data.get("add"), "port": int(data.get("port", 0)), "ps": data.get("ps", ""), "link": link}
        if link.startswith("vless://"):
            parsed = urllib.parse.urlparse(link)
            return {"host": parsed.hostname, "port": parsed.port or 443, "ps": parsed.fragment or "", "link": link}
    except: return None

def is_target_name(ps):
    ps = (ps or "").upper()
    targets = ["US", "USA", "AMERICA", "UK", "GB", "LONDON", "CA", "CANADA", "TORONTO", "🇺🇸", "🇬🇧", "🇨🇦"]
    return any(t in ps for t in targets)

def check_connectivity(node):
    """High-speed parallel connectivity check."""
    try:
        # Step 1: DNS Resolution
        addr = socket.gethostbyname(node["host"])
        # Step 2: TCP Handshake
        sock = socket.create_connection((addr, node["port"]), timeout=TCP_TIMEOUT)
        sock.close()
        return node
    except:
        return None

def get_country(host, cache):
    if host in cache: return cache[host]
    time.sleep(GEOIP_RATE_LIMIT)
    try:
        # Strict Geo-IP lookup
        r = requests.get(f"http://ip-api.com/json/{host}?fields=countryCode", timeout=10)
        code = r.json().get("countryCode", "").upper()
        cache[host] = code
        return code
    except: return None

def main():
    print("=== DEEP RESEARCH START ===")
    raw_data = ""
    for url in SUBSCRIPTION_URLS:
        print(f"[*] Fetching: {url[:50]}...")
        raw = fetch_url(url)
        if raw: raw_data += raw + "\n"
    
    all_links = decode_sub(raw_data)
    print(f"[+] Total unique links: {len(all_links)}")
    
    # 1. Filter by Name
    candidates = []
    for l in all_links[:MAX_LINKS_TO_PROCESS]:
        p = parse_link(l)
        if p and is_target_name(p["ps"]):
            candidates.append(p)
    print(f"[+] Found {len(candidates)} CA/US/UK candidates.")

    if not candidates:
        print("[-] No matching nodes found.")
        return

    # 2. Connectivity Test (30 threads for speed)
    print("[*] Testing connectivity...")
    working_nodes = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(check_connectivity, c) for c in candidates]
        for fut in as_completed(futures):
            res = fut.result()
            if res: working_nodes.append(res)
    
    print(f"[+] {len(working_nodes)} nodes are online.")

    # 3. Strict Geo-IP Verification
    final_links = []
    geo_cache = {}
    print(f"[*] Strict Location Verification (Target: {MAX_VERIFIED_NODES})...")
    
    for node in working_nodes:
        if len(final_links) >= MAX_VERIFIED_NODES: break
        
        country = get_country(node["host"], geo_cache)
        if country in STRICT_ALLOWED_COUNTRIES:
            final_links.append(node["link"])
            print(f"  [VERIFIED] Server physically located in {country}")
        else:
            print(f"  [REJECTED] IP actually in {country or 'Unknown'}")

    # Save results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_links))
    
    print(f"\n[DONE] Saved {len(final_links)} strictly verified nodes to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
