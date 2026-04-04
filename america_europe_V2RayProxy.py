#!/usr/bin/env python3
from __future__ import annotations

"""
ULTIMATE CA, US, UK V2Ray Proxy Fetcher (Maximum GitHub Database Edition)
Deeply scrapes tens of thousands of free V2Ray (VMess/VLESS) configs from the 
largest daily-updated GitHub public subscriptions in existence.
STRICTLY enforces Canada, USA, and UK nodes ONLY. 
Uses an aggressive Hybrid Name-Check + Live TCP Test + Strict GeoIP Verification 
pipeline to guarantee absolutely NO other countries are allowed at any cost.
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

# Ensure requests is installed for network calls
try:
    import requests
except ImportError:
    print("Installing required package: requests")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# Optional: pyperclip for automatic clipboard copying
try:
    import pyperclip
except ImportError:
    pyperclip = None

# Optional: real VMess/VLESS handshake testing
USE_STRICT_TEST = True
_v2ray_tester = None
_v2ray_available = None

# ---------------------------------------------------------------------------
# THE MASTER LIST: The deepest, largest, most reliable V2Ray subscription 
# aggregators currently active on GitHub. (150,000+ nodes combined)
# ---------------------------------------------------------------------------
SUBSCRIPTION_URLS =[
    # The Absolute Giants
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/vless",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/vmess",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vless",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vmess",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription1",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription2",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription3",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription4",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription5",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription6",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription7",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription8",
    
    # Premium Quality Aggregators & Scrapers
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/ts-sf/fly/main/v2",
    "https://raw.githubusercontent.com/Alireza-ok/xray/main/mix",
    "https://raw.githubusercontent.com/Barati-1996/v2ray-config/main/Sub.txt",
    "https://raw.githubusercontent.com/mzz2017/gg/main/v2ray/v2ray.txt",
    "https://raw.githubusercontent.com/freev2rayconfig/V2RAY_SUBSCRIPTION_LINK/main/v2rayconfigs.txt",
    "https://raw.githubusercontent.com/yitong2333/proxy-minging/main/v2ray.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/tbbatbb/Proxy/master/manual/v2ray.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/v2ray-links/v2ray-free-proxy/main/v2ray-free-proxy.txt",
    "https://raw.githubusercontent.com/Leon406/Sub/master/sub/share/vless",
    "https://raw.githubusercontent.com/Leon406/Sub/master/sub/share/vmess",
    "https://raw.githubusercontent.com/Lexiie/V2ray-Configs/main/Sub.txt",
    
    # Standard & Focused Repos
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/all_configs.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/sakha1370/OpenRay/refs/heads/main/output/all_valid_proxies.txt",
    "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vl.txt",
    "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vm.txt",
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
    "https://raw.githubusercontent.com/CidVpn/cid-vpn-config/refs/heads/main/general.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/all_extracted_configs.txt",
    "https://raw.githubusercontent.com/wuqb2i4f/xray-config-toolkit/main/output/base64/mix-uri",
    "https://raw.githubusercontent.com/acymz/AutoVPN/refs/heads/main/data/V2.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vless.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/Bardiafa/Free-V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/Bardiafa/Free-V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/LonUp/NodeList/main/V2RAY/Latest.txt"
]

GEOIP_RATE_LIMIT = 1.35  # Respect IP-API rate limits to avoid ban
TCP_TIMEOUT = 4          # Aggressive timeout: if it takes more than 4s to connect, drop it
FETCH_TIMEOUT = 25
MAX_WORKERS = 20
MAX_LINKS_TO_PROCESS = 100000  # Built to handle massive lists

# STRICT ALLOWLIST: Absolutely no other countries.
# GB is the ISO standard code for the United Kingdom.
CANADA_CODES = {"CA"}
USA_CODES = {"US"}
UK_CODES = {"GB", "UK"}

STRICT_ALLOWED_COUNTRIES = CANADA_CODES | USA_CODES | UK_CODES


def out_dir():
    return Path(__file__).resolve().parent

def _ensure_strict_tester():
    global _v2ray_available
    if _v2ray_available is False:
        return None, None
    try:
        from python_v2ray.downloader import BinaryDownloader
        from python_v2ray.tester import ConnectionTester
        from python_v2ray.config_parser import parse_uri as pv2_parse_uri
        base = out_dir()
        vendor = base / "vendor"
        core_engine = base / "core_engine"
        downloader = BinaryDownloader(base)
        downloader.ensure_all()
        tester = ConnectionTester(
            vendor_path=str(vendor),
            core_engine_path=str(core_engine),
        )
        _v2ray_available = True
        return tester, pv2_parse_uri
    except Exception:
        _v2ray_available = False
        return None, None

def test_nodes_strict(links: list[str]) -> tuple[list[str], list[dict]]:
    tester, parse_uri_fn = _ensure_strict_tester()
    if not tester or not parse_uri_fn:
        return [],[]
    parsed = []
    valid_links =[]
    for uri in links:
        try:
            p = parse_uri_fn(uri)
            if p:
                parsed.append(p)
                valid_links.append(uri)
        except Exception:
            pass
    if not parsed:
        return [],[]
    try:
        results = tester.test_uris(parsed)
    except Exception:
        return [], []
    working_links = [
        valid_links[i] for i, r in enumerate(results)
        if i < len(valid_links) and r.get("status") == "success"
    ]
    return working_links, results

def fetch_url(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=FETCH_TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  [skip] Could not reach {url[:45]}...")
        return None

def decode_subscription(raw: str) -> list[str]:
    links =[]
    text = raw.strip()
    for chunk in text.split():
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            decoded = base64.b64decode(chunk + "==").decode("utf-8", errors="ignore")
            for line in decoded.splitlines():
                line = line.strip()
                if line.startswith("vmess://") or line.startswith("vless://"):
                    links.append(line)
        except Exception:
            pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vmess://") or line.startswith("vless://"):
            links.append(line)
    return list(dict.fromkeys(links))

def parse_vmess(link: str) -> dict | None:
    if not link.startswith("vmess://"):
        return None
    try:
        b64 = link[8:].strip()
        padded = b64 + "=="
        data = base64.b64decode(padded).decode("utf-8", errors="replace")
        obj = json.loads(data)
        host = obj.get("add") or obj.get("host") or ""
        port = int(obj.get("port", 0))
        uid = (obj.get("id") or "").strip()
        if not host or not port:
            return None
        return {"type": "vmess", "host": host, "port": port, "uuid": uid, "link": link, "ps": obj.get("ps", "")}
    except Exception:
        return None

def parse_vless(link: str) -> dict | None:
    if not link.startswith("vless://"):
        return None
    try:
        parsed = urllib.parse.urlparse(link)
        host = parsed.hostname or ""
        port = parsed.port or 443
        netloc = parsed.netloc or ""
        uid = (netloc.split("@")[0] if "@" in netloc else "").strip()
        if not host:
            return None
        return {"type": "vless", "host": host, "port": port, "uuid": uid, "link": link, "ps": (parsed.fragment or "")}
    except Exception:
        return None

def parse_link(link: str) -> dict | None:
    return parse_vmess(link) or parse_vless(link)

def is_target_country_name(ps: str) -> bool:
    """FIREWALL 1: Name Pre-filter. Destroys anything not claiming to be CA/US/UK."""
    ps_upper = (" " + (ps or "") + " ").upper()
    
    # Replace separators with spaces to ensure exact word matches
    for char in["-", "_", "|", ":", "[", "]", "(", ")", "，", ",", ".", "/"]:
        ps_upper = ps_upper.replace(char, " ")
    
    words = set(ps_upper.split())
    
    ca_keywords = {"CA", "CANADA", "TORONTO", "MONTREAL", "VANCOUVER"}
    us_keywords = {"US", "USA", "AMERICA", "UNITED", "STATES"}
    uk_keywords = {"UK", "GB", "LONDON", "KINGDOM", "BRITAIN"}
    
    if "UNITED STATES" in ps_upper or "UNITED KINGDOM" in ps_upper or "GREAT BRITAIN" in ps_upper:
        return True
    
    # Check Emoji Flags
    if "🇨🇦" in ps_upper or "🇺🇸" in ps_upper or "🇬🇧" in ps_upper:
        return True
        
    if ca_keywords.intersection(words) or us_keywords.intersection(words) or uk_keywords.intersection(words):
        return True
        
    return False

def get_country_strict(host: str, cache: dict) -> str | None:
    """FIREWALL 3: Real IP Geo-Location. Guarantees no fakes slip through."""
    if host in cache:
        return cache[host]
    
    time.sleep(GEOIP_RATE_LIMIT)
    try:
        # IP-API verifies the physical data center location of the server IP
        r = requests.get(
            f"http://ip-api.com/json/{host}?fields=countryCode,status",
            timeout=8,
        )
        data = r.json()
        if data.get("status") == "success":
            code = (data.get("countryCode") or "").upper()
            cache[host] = code
            return code
    except Exception:
        pass
    
    cache[host] = None
    return None

def region_priority(node: dict) -> int:
    """Orders the final output strictly as: Canada (0), USA (1), UK (2)"""
    country = (node.get("country") or "").upper()
    if country in CANADA_CODES:
        return 0
    if country in USA_CODES:
        return 1
    if country in UK_CODES:
        return 2
    return 99 # Failsafe

def test_tcp(host: str, port: int) -> bool:
    """FIREWALL 2: Connectivity Check. Drops offline servers immediately."""
    try:
        sock = socket.create_connection((host, port), timeout=TCP_TIMEOUT)
        sock.close()
        return True
    except (socket.timeout, OSError, socket.gaierror):
        return False

def main():
    print("===================================================================")
    print(" ULTIMATE CA, US, UK STRICT V2RAY FETCHER (Massive Data Edition) ")
    print("===================================================================\n")
    base = out_dir()
    print(f"Directory: {base}\n")

    print("[*] STEP 1/4: Deep Scraping GitHub Databases...")
    all_links =[]
    for url in SUBSCRIPTION_URLS:
        raw = fetch_url(url)
        if raw:
            links = decode_subscription(raw)
            all_links.extend(links)
            
    all_links = list(dict.fromkeys(all_links))
    print(f"\n[+] Massive Extraction Complete: {len(all_links)} total unique config links found.")
    
    if len(all_links) > MAX_LINKS_TO_PROCESS:
        all_links = all_links[:MAX_LINKS_TO_PROCESS]

    if not all_links:
        print("[-] No links found. Check your internet connection.")
        return

    print("\n[*] STEP 2/4: Applying Name Firewall (Identifying CA/US/UK nodes)...")
    potential_nodes =[]
    for link in all_links:
        node = parse_link(link)
        if node and is_target_country_name(node["ps"]):
            potential_nodes.append(node)
            
    print(f"[+] Destroyed {len(all_links) - len(potential_nodes)} irrelevant nodes.")
    print(f"[+] Remaining CA/US/UK Candidates: {len(potential_nodes)}")
    
    if not potential_nodes:
        print("[-] No CA/US/UK nodes found in this massive scrape. Try again later.")
        return

    print("\n[*] STEP 3/4: Live Testing Connectivity (Deleting Dead Nodes)...")
    working_nodes = []
    links_only_for_test = [n["link"] for n in potential_nodes]

    # Try deep V2Ray protocol testing if the user has the module installed
    if USE_STRICT_TEST:
        working_links, strict_results = test_nodes_strict(links_only_for_test)
        if working_links:
            working_nodes =[n for n in potential_nodes if n["link"] in working_links]
            for r in (strict_results or[]):
                if r.get("status") == "success":
                    print(f"  [ONLINE] {r.get('tag', '')[:40]}... | Latency: {r.get('ping_ms', -1)} ms")

    # TCP testing fallback / primary execution
    if not working_nodes:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_tcp, n["host"], n["port"]): n for n in potential_nodes}
            for i, fut in enumerate(as_completed(futures)):
                node = futures[fut]
                try:
                    if fut.result():
                        working_nodes.append(node)
                        print(f"  [ONLINE] {node['ps'][:40]} ({node['host']}:{node['port']})")
                except Exception:
                    pass

    print(f"\n[+] Working, responsive servers found: {len(working_nodes)}")
    
    if not working_nodes:
        print("[-] All candidates were offline or blocked. Script finished.")
        return

    print("\n[*] STEP 4/4: Absolute Geo-IP Verification (Destroying Fakes)...")
    print("    Warning: Tracing IPs to physical datacenters. Dropping ANY exceptions.")
    
    final_strict_nodes =[]
    geo_cache = {}
    
    for i, node in enumerate(working_nodes):
        country = get_country_strict(node["host"], geo_cache)
        
        # -------------------------------------------------------------------
        # THE ULTIMATE RULE: At Any Cost, Destroy Non-Target Locations
        # -------------------------------------------------------------------
        if country in STRICT_ALLOWED_COUNTRIES:
            node["country"] = country
            final_strict_nodes.append(node)
            print(f"  [VERIFIED] Server in {country} -> {node['ps'][:30]}")
        else:
            print(f"  [DESTROYED] Fake location detected! Real IP is in {country or 'Unknown'}. Dropped.")
            
    print(f"\n===================================================================")
    print(f" FINAL RESULT: {len(final_strict_nodes)} 100% VERIFIED, ONLINE NODES")
    print(f"===================================================================")

    if not final_strict_nodes:
        print("[-] No nodes survived the Geo-IP Verification. All were fakes.")
        return

    # Sort them explicitly: Canada -> USA -> UK
    final_strict_nodes.sort(key=region_priority)
    
    n_ca = sum(1 for n in final_strict_nodes if n["country"] in CANADA_CODES)
    n_us = sum(1 for n in final_strict_nodes if n["country"] in USA_CODES)
    n_uk = sum(1 for n in final_strict_nodes if n["country"] in UK_CODES)
    print(f" Breakdown: Canada[{n_ca}], USA [{n_us}], UK [{n_uk}]")

    # Remove identical duplicate configurations
    seen_key: dict[tuple[str, int, str], str] = {}
    for n in final_strict_nodes:
        key = (n["host"], n["port"], n.get("uuid") or "")
        if key not in seen_key:
            seen_key[key] = n["link"]
            
    links_only = list(seen_key.values())
    
    content = "\n".join(links_only)
    out_file = base / "hiddify_ca_us_uk.txt"
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[+] Saved flawlessly verified nodes to: {out_file.name}")

    # Auto-copy to clipboard
    in_ci = os.environ.get("CI") == "true"
    if not in_ci and pyperclip:
        try:
            pyperclip.copy(content)
            print("[+] Successfully copied all links to your clipboard!")
        except Exception as e:
            print(f"[-] Clipboard copy failed: {e}. Please open {out_file.name} to copy manually.")
    elif not in_ci:
        print("\nTip: Install 'pyperclip' (pip install pyperclip) to auto-copy to your clipboard.")
        print(f"For now, open {out_file.name}, select all, copy, and paste into Hiddify.")

    print("\nTask complete. Paste from clipboard into Hiddify or v2rayN!")

if __name__ == "__main__":
    main()
