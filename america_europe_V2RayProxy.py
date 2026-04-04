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
MAX_LINKS_TO_PROCESS = 60000
MAX_VERIFIED_NODES = 100
GEOIP_RATE_LIMIT = 1.35
TCP_TIMEOUT = 5
OUTPUT_FILE = "hiddify_ca_us_uk.txt"

Path(OUTPUT_FILE).touch()

SUBSCRIPTION_URLS = [
    # High-frequency sources (every 5-15 min)
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/all_extracted_configs.txt",
    "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/vless.txt",
    "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/vmess.txt",
    # Country-pre-filtered (US/UK/CA)
    "https://raw.githubusercontent.com/Epodonios/bulk-xray-v2ray-vless-vmess-...-configs/main/sub/United%20States/config.txt",
    "https://raw.githubusercontent.com/Epodonios/bulk-xray-v2ray-vless-vmess-...-configs/main/sub/United%20Kingdom/config.txt",
    "https://raw.githubusercontent.com/Epodonios/bulk-xray-v2ray-vless-vmess-...-configs/main/sub/Canada/config.txt",
    # Aggregators updated every few hours
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
    "https://raw.githubusercontent.com/Turbine8845/telegram-configs-collector/main/protocols/vless",
    "https://raw.githubusercontent.com/Turbine8845/telegram-configs-collector/main/protocols/vmess",
    "https://raw.githubusercontent.com/MrMohebi/xray-proxy-grabber-telegram/master/collected-proxies/row-url/all.txt",
    "https://raw.githubusercontent.com/4n0nymou3/multi-proxy-config-fetcher/main/configs/proxy_configs.txt",
    "https://raw.githubusercontent.com/hamedcode/port-based-v2ray-configs/main/all.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/freev2rayconfig/V2RAY_SUBSCRIPTION_LINK/main/v2rayconfigs.txt",
]

STRICT_ALLOWED_COUNTRIES = {"CA", "US", "GB"}

# US East Coast city/state keywords — lowest latency from India
US_EAST_KEYWORDS = [
    "NY", "NEW YORK", "NJ", "NEW JERSEY", "VA", "VIRGINIA",
    "DC", "WASHINGTON", "ATL", "ATLANTA", "NC", "CAROLINA",
    "FL", "FLORIDA", "MA", "BOSTON", "PA", "PHILADELPHIA",
    "OH", "OHIO", "GA", "GEORGIA", "MD", "MARYLAND"
]

def fetch_url(url):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        return r.text if r.status_code == 200 else None
    except:
        return None

def decode_sub(raw):
    links = []
    if not raw:
        return []
    for chunk in raw.split():
        try:
            decoded = base64.b64decode(chunk + "==").decode("utf-8", errors="ignore")
            for line in decoded.splitlines():
                if line.startswith(("vmess://", "vless://")):
                    links.append(line.strip())
        except:
            pass
    for line in raw.splitlines():
        if line.startswith(("vmess://", "vless://")):
            links.append(line.strip())
    return list(set(links))

def parse_link(link):
    try:
        if link.startswith("vmess://"):
            data = json.loads(base64.b64decode(link[8:] + "==").decode("utf-8"))
            return {
                "host": data.get("add"),
                "port": int(data.get("port", 0)),
                "ps": data.get("ps", ""),
                "net": data.get("net", ""),
                "security": data.get("tls", ""),
                "is_reality": False,  # VMess cannot be Reality
                "link": link
            }
        if link.startswith("vless://"):
            parsed = urllib.parse.urlparse(link)
            params = urllib.parse.parse_qs(parsed.query)
            security = params.get("security", [""])[0].lower()
            net = params.get("type", [""])[0].lower()
            return {
                "host": parsed.hostname,
                "port": parsed.port or 443,
                "ps": urllib.parse.unquote(parsed.fragment or ""),
                "net": net,
                "security": security,
                "is_reality": security == "reality",
                "link": link
            }
    except:
        return None

def is_target_name(ps):
    ps = (ps or "").upper()
    targets = [
        "US", "USA", "AMERICA", "UNITED STATES",
        "UK", "GB", "LONDON", "ENGLAND", "BRITAIN",
        "CA", "CANADA", "TORONTO", "VANCOUVER", "MONTREAL",
        "🇺🇸", "🇬🇧", "🇨🇦"
    ]
    return any(t in ps for t in targets)

def is_east_coast_us(ps):
    ps = (ps or "").upper()
    return any(k in ps for k in US_EAST_KEYWORDS)

def check_connectivity_with_rtt(node):
    """TCP connectivity check that also measures RTT."""
    try:
        addr = socket.gethostbyname(node["host"])
        start = time.time()
        sock = socket.create_connection((addr, node["port"]), timeout=TCP_TIMEOUT)
        rtt = (time.time() - start) * 1000
        sock.close()
        node["rtt"] = round(rtt, 2)
        node["ip"] = addr
        return node
    except:
        return None

def get_country(host, ip, cache):
    key = ip or host
    if key in cache:
        return cache[key]
    time.sleep(GEOIP_RATE_LIMIT)
    try:
        target = ip if ip else host
        r = requests.get(
            f"http://ip-api.com/json/{target}?fields=countryCode,city,isp",
            timeout=10
        )
        data = r.json()
        code = data.get("countryCode", "").upper()
        city = data.get("city", "")
        isp = data.get("isp", "")
        cache[key] = (code, city, isp)
        return (code, city, isp)
    except:
        return (None, "", "")

def main():
    print("=== V2RAY FETCHER: US/UK/CA STRICT MODE (REALITY PRIORITY) ===")
    print(f"Sources: {len(SUBSCRIPTION_URLS)} | Target: {MAX_VERIFIED_NODES} verified nodes\n")

    # --- Step 1: Fetch all sources ---
    raw_data = ""
    for url in SUBSCRIPTION_URLS:
        print(f"[*] Fetching: {url[:70]}...")
        raw = fetch_url(url)
        if raw:
            raw_data += raw + "\n"
        else:
            print(f"    [SKIP] Failed or empty.")

    all_links = decode_sub(raw_data)
    print(f"\n[+] Total unique links found: {len(all_links)}")

    # --- Step 2: Filter by name keywords ---
    candidates = []
    for l in all_links[:MAX_LINKS_TO_PROCESS]:
        p = parse_link(l)
        if not p or not p["host"]:
            continue
        if is_target_name(p["ps"]):
            p["east_coast"] = is_east_coast_us(p["ps"])
            p["ws_penalty"] = p.get("net") == "ws"
            candidates.append(p)

    # --- Priority sort ---
    # 1st: VLESS+Reality  (fastest, most stable)
    # 2nd: East Coast US  (lowest latency from India)
    # 3rd: non-WebSocket  (less overhead)
    # 4th: everything else
    candidates.sort(key=lambda x: (
        not x.get("is_reality"),
        not x.get("east_coast"),
        x.get("ws_penalty"),
    ))

    reality_count = sum(1 for c in candidates if c.get("is_reality"))
    east_count = sum(1 for c in candidates if c.get("east_coast"))
    print(f"[+] Candidates after name filter : {len(candidates)}")
    print(f"    VLESS+Reality nodes found     : {reality_count}")
    print(f"    East Coast US nodes boosted   : {east_count}")

    if not candidates:
        print("[-] No matching nodes found. Exiting.")
        return

    # --- Step 3: Parallel TCP connectivity + RTT ---
    print(f"\n[*] Testing connectivity with RTT (50 threads)...")
    working_nodes = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(check_connectivity_with_rtt, c) for c in candidates]
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                working_nodes.append(res)

    # Sort by RTT ascending within each priority tier
    working_nodes.sort(key=lambda x: (
        not x.get("is_reality"),
        not x.get("east_coast"),
        x.get("ws_penalty"),
        x.get("rtt", 9999)
    ))

    print(f"[+] {len(working_nodes)} nodes responded.")
    print(f"    Top 5 fastest nodes:")
    for n in working_nodes[:5]:
        tag = "REALITY" if n.get("is_reality") else n.get("net", "").upper()
        print(f"    [{tag}] {n['host']} | {n['rtt']}ms | {n['ps'][:40]}")

    # --- Step 4: Strict GeoIP verification (fastest/best first) ---
    final_links = []
    geo_cache = {}
    print(f"\n[*] GeoIP verification (target={MAX_VERIFIED_NODES})...")

    for node in working_nodes:
        if len(final_links) >= MAX_VERIFIED_NODES:
            break

        country, city, isp = get_country(node["host"], node.get("ip"), geo_cache)

        if country in STRICT_ALLOWED_COUNTRIES:
            final_links.append(node["link"])
            flag = {"US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦"}.get(country, "")
            tag = "REALITY" if node.get("is_reality") else node.get("net", "").upper()
            print(f"  [✓] {flag} {country} | {city} | {node['rtt']}ms | [{tag}] | {isp[:25]}")
        else:
            print(f"  [✗] REJECTED — actually {country or 'Unknown'} ({node['host']})")

    # --- Step 5: Save ---
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final_links))

    # --- Summary ---
    reality_saved = sum(1 for n in working_nodes[:len(final_links)] if n.get("is_reality"))
    print(f"\n{'='*55}")
    print(f"[DONE] Saved {len(final_links)} verified nodes to {OUTPUT_FILE}")
    print(f"       VLESS+Reality nodes in output : {reality_saved}")
    print(f"       Other nodes in output         : {len(final_links) - reality_saved}")

if __name__ == "__main__":
    main()
