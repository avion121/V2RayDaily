#!/usr/bin/env python3
from __future__ import annotations

"""
TURBO CA, US, UK V2Ray Proxy Fetcher
Optimized for Speed: Parallel Fetching + Batch GeoIP + High-Concurrency Testing.
STRICTLY enforces Canada, USA, and UK nodes ONLY.
"""

import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# Optimization Constants
MAX_FETCH_WORKERS = 15
MAX_TEST_WORKERS = 50  # Increased for speed
TCP_TIMEOUT = 3.5
FETCH_TIMEOUT = 15
MAX_LINKS_TO_PROCESS = 80000

# Strict Allowlist
CANADA_CODES = {"CA"}
USA_CODES = {"US"}
UK_CODES = {"GB", "UK"}
STRICT_ALLOWED_COUNTRIES = CANADA_CODES | USA_CODES | UK_CODES

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
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vless.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vmess.txt",
    "https://raw.githubusercontent.com/LonUp/NodeList/main/V2RAY/Latest.txt"
]

def decode_subscription(raw: str) -> list[str]:
    links = []
    text = raw.strip()
    # Handle Base64 encoded subscriptions
    try:
        if not text.startswith(('vmess://', 'vless://')):
            text = base64.b64decode(text + "==").decode("utf-8", errors="ignore")
    except: pass
    
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("vmess://", "vless://")):
            links.append(line)
    return links

def fetch_all_parallel():
    all_links = []
    def fetch_one(url):
        try:
            r = requests.get(url, timeout=FETCH_TIMEOUT)
            return decode_subscription(r.text) if r.status_code == 200 else []
        except: return []

    with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as executor:
        futures = [executor.submit(fetch_one, url) for url in SUBSCRIPTION_URLS]
        for fut in as_completed(futures):
            all_links.extend(fut.result())
    return list(dict.fromkeys(all_links))

def parse_link(link: str) -> dict | None:
    try:
        if link.startswith("vmess://"):
            data = json.loads(base64.b64decode(link[8:] + "==").decode("utf-8"))
            return {"host": data.get("add"), "port": int(data.get("port", 0)), "ps": data.get("ps", ""), "link": link}
        elif link.startswith("vless://"):
            parsed = urllib.parse.urlparse(link)
            return {"host": parsed.hostname, "port": parsed.port or 443, "ps": parsed.fragment, "link": link}
    except: return None

def is_target_name(ps: str) -> bool:
    ps_up = (" " + (ps or "") + " ").upper()
    targets = {"CA", "CANADA", "US", "USA", "AMERICA", "UK", "GB", "LONDON", "KINGDOM", "TORONTO", "🇺🇸", "🇨🇦", "🇬🇧"}
    return any(t in ps_up for t in targets)

def test_tcp(node: dict) -> dict | None:
    try:
        with socket.create_connection((node["host"], node["port"]), timeout=TCP_TIMEOUT):
            return node
    except: return None

def verify_geo_batch(nodes: list[dict]) -> list[dict]:
    """VERIFICATION TURBO: Checks 100 IPs in one single request."""
    if not nodes: return []
    verified = []
    # Extract unique hosts
    hosts = list({n["host"] for n in nodes})
    host_to_country = {}

    # ip-api batch allows 100 per request
    for i in range(0, len(hosts), 100):
        batch = hosts[i : i + 100]
        try:
            r = requests.post("http://ip-api.com/batch?fields=query,countryCode", json=batch, timeout=15)
            for item in r.json():
                host_to_country[item["query"]] = item.get("countryCode", "")
        except: pass
        time.sleep(1.5) # Wait for batch limit (15 requests/min)

    for n in nodes:
        code = host_to_country.get(n["host"], "")
        if code in STRICT_ALLOWED_COUNTRIES:
            n["country"] = code
            verified.append(n)
    return verified

def main():
    print("[1/4] Turbo Fetching GitHub Repos...")
    raw_links = fetch_all_parallel()
    print(f"[*] Found {len(raw_links)} raw links.")

    print("[2/4] Filtering names (CA/US/UK only)...")
    candidates = []
    for link in raw_links[:MAX_LINKS_TO_PROCESS]:
        node = parse_link(link)
        if node and is_target_name(node["ps"]):
            candidates.append(node)
    
    print(f"[*] {len(candidates)} candidates found. Testing connectivity...")

    print("[3/4] Testing {len(candidates)} nodes in parallel...")
    working = []
    with ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as executor:
        futures = [executor.submit(test_tcp, n) for n in candidates]
        for fut in as_completed(futures):
            res = fut.result()
            if res: working.append(res)
    
    print(f"[*] {len(working)} nodes online. Starting Batch Geo-Verification...")

    print("[4/4] Final Geo-IP Strict Check (Batch Mode)...")
    final = verify_geo_batch(working)
    
    # Sort CA -> US -> UK
    priority = {"CA": 0, "US": 1, "GB": 2, "UK": 2}
    final.sort(key=lambda x: priority.get(x["country"], 9))

    # Remove duplicates and save
    seen = set()
    result_links = []
    for n in final:
        key = (n["host"], n["port"])
        if key not in seen:
            seen.add(key)
            result_links.append(n["link"])

    Path("hiddify_ca_us_uk.txt").write_text("\n".join(result_links))
    print(f"\nDONE! {len(result_links)} strictly verified nodes saved to hiddify_ca_us_uk.txt")

if __name__ == "__main__":
    main()
