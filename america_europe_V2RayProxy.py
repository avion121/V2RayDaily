#!/usr/bin/env python3
import base64, json, os, socket, subprocess, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- CONFIGURATION ---
USE_STRICT_TEST = True
# WE REDUCE THESE TO ENSURE < 10 MINUTE RUNTIME
MAX_LINKS_TO_PROCESS = 25000 
MAX_VERIFIED_NODES = 100  # Stop after finding 100 verified CA/US/UK nodes
GEOIP_RATE_LIMIT = 1.35 
TCP_TIMEOUT = 3

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
        r = requests.get(url, timeout=15)
        return r.text if r.status_code == 200 else None
    except: return None

def decode_sub(raw):
    links = []
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
            return {"host": parsed.hostname, "port": parsed.port or 443, "ps": parsed.fragment, "link": link}
    except: return None

def is_target_name(ps):
    ps = ps.upper()
    targets = ["US", "USA", "AMERICA", "UK", "GB", "LONDON", "CA", "CANADA", "TORONTO", "🇺🇸", "🇬🇧", "🇨🇦"]
    return any(t in ps for t in targets)

def test_nodes_strict(links):
    try:
        from python_v2ray.downloader import BinaryDownloader
        from python_v2ray.tester import ConnectionTester
        from python_v2ray.config_parser import parse_uri
        dl = BinaryDownloader(Path(__file__).parent)
        dl.ensure_all()
        tester = ConnectionTester(vendor_path=str(Path(__file__).parent / "vendor"), core_engine_path=str(Path(__file__).parent / "core_engine"))
        parsed = [parse_uri(l) for l in links if parse_uri(l)]
        results = tester.test_uris(parsed)
        return [links[i] for i, r in enumerate(results) if r.get("status") == "success"]
    except: return []

def get_country(host, cache):
    if host in cache: return cache[host]
    time.sleep(GEOIP_RATE_LIMIT)
    try:
        data = requests.get(f"http://ip-api.com/json/{host}?fields=countryCode", timeout=5).json()
        code = data.get("countryCode", "").upper()
        cache[host] = code
        return code
    except: return None

def main():
    print("[*] Starting Optimized Fetch (Target: < 10 mins)")
    raw_data = ""
    for url in SUBSCRIPTION_URLS:
        raw = fetch_url(url)
        if raw: raw_data += raw + "\n"
    
    all_links = decode_sub(raw_data)[:MAX_LINKS_TO_PROCESS]
    candidates = [n for n in [parse_link(l) for l in all_links] if n and is_target_name(n["ps"])]
    print(f"[+] Found {len(candidates)} candidates.")

    working_links = test_nodes_strict([c["link"] for c in candidates])
    if not working_links:
        print("[-] No working nodes found via protocol test.")
        return

    working_nodes = [n for n in candidates if n["link"] in working_links]
    final_nodes = []
    geo_cache = {}

    print(f"[*] Verifying locations (Stop at {MAX_VERIFIED_NODES})...")
    for node in working_nodes:
        if len(final_nodes) >= MAX_VERIFIED_NODES: break
        country = get_country(node["host"], geo_cache)
        if country in STRICT_ALLOWED_COUNTRIES:
            node["country"] = country
            final_nodes.append(node["link"])
            print(f"  [OK] {country} confirmed.")
        else:
            print(f"  [SKIP] {country or 'Unknown'}")

    with open("hiddify_ca_us_uk.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(final_nodes))
    print(f"\n[+] Done! Saved {len(final_nodes)} verified nodes.")

if __name__ == "__main__":
    main()
