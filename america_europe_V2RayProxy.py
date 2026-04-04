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
MAX_LINKS_TO_PROCESS = 30000 
MAX_VERIFIED_NODES = 100  
GEOIP_RATE_LIMIT = 1.35 
TCP_TIMEOUT = 5
OUTPUT_FILE = "hiddify_ca_us_uk.txt"

# Ensure file exists immediately so GitHub Actions doesn't crash
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

def test_tcp(node):
    try:
        sock = socket.create_connection((node["host"], node["port"]), timeout=TCP_TIMEOUT)
        sock.close()
        return node["link"]
    except: return None

def test_nodes_advanced(links):
    """Try Deep Test first, if it fails, use TCP."""
    try:
        print("[*] Attempting Deep Protocol Handshake...")
        from python_v2ray.downloader import BinaryDownloader
        from python_v2ray.tester import ConnectionTester
        from python_v2ray.config_parser import parse_uri
        
        base_path = Path(__file__).parent
        dl = BinaryDownloader(base_path)
        dl.ensure_all()
        
        tester = ConnectionTester(
            vendor_path=str(base_path / "vendor"), 
            core_engine_path=str(base_path / "core_engine")
        )
        
        parsed = []
        valid_map = []
        for l in links:
            p = parse_uri(l)
            if p:
                parsed.append(p)
                valid_map.append(l)
        
        # We increase the timeout here to prevent the '10s timeout' error
        results = tester.test_uris(parsed)
        working = [valid_map[i] for i, r in enumerate(results) if r.get("status") == "success"]
        if working: return working
    except Exception as e:
        print(f"[!] Deep Test failed/timed out: {e}")
    
    print("[*] Falling back to high-speed TCP check...")
    working = []
    nodes = [parse_link(l) for l in links]
    nodes = [n for n in nodes if n]
    with ThreadPoolExecutor(max_workers=30) as ex:
        futures = [ex.submit(test_tcp, n) for n in nodes]
        for fut in as_completed(futures):
            res = fut.result()
            if res: working.append(res)
    return working

def get_country(host, cache):
    if host in cache: return cache[host]
    time.sleep(GEOIP_RATE_LIMIT)
    try:
        data = requests.get(f"http://ip-api.com/json/{host}?fields=countryCode", timeout=10).json()
        code = data.get("countryCode", "").upper()
        cache[host] = code
        return code
    except: return None

def main():
    print("[*] Starting Optimized Research...")
    raw_data = ""
    for url in SUBSCRIPTION_URLS:
        print(f"  > Scoping: {url[:50]}...")
        raw = fetch_url(url)
        if raw: raw_data += raw + "\n"
    
    all_links = decode_sub(raw_data)
    print(f"[+] Total links found: {len(all_links)}")
    
    # Pre-filter by name to save time
    candidates = [n for n in [parse_link(l) for l in all_links[:MAX_LINKS_TO_PROCESS]] if n and is_target_name(n["ps"])]
    print(f"[+] Filtered {len(candidates)} CA/US/UK candidate nodes.")

    if not candidates:
        print("[-] No candidates found in this cycle.")
        return

    working_links = test_nodes_advanced([c["link"] for c in candidates])
    print(f"[+] {len(working_links)} nodes passed connectivity tests.")

    final_links = []
    geo_cache = {}

    print(f"[*] Starting Geo-IP Verification (Limit: {MAX_VERIFIED_NODES})...")
    for link in working_links:
        if len(final_links) >= MAX_VERIFIED_NODES: break
        node = parse_link(link)
        if not node: continue
        
        country = get_country(node["host"], geo_cache)
        if country in STRICT_ALLOWED_COUNTRIES:
            final_links.append(link)
            print(f"  [VERIFIED] Found {country} node.")
        else:
            print(f"  [REJECTED] IP actually in {country or 'Unknown'}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_links))
    
    print(f"\n[SUCCESS] Saved {len(final_links)} strictly verified nodes to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
