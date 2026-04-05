#!/usr/bin/env python3
import base64, json, socket, subprocess, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# --- AUTO INSTALL REQUESTS ---
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- CONFIGURATION ---
MAX_LINKS_TO_TEST = 4000     # How many links to ping test (Higher = better results, but takes longer)
MAX_PER_LIST = 100           # Max nodes per output file
TCP_TIMEOUT = 2.5            # 2.5s timeout. We only want FAST nodes.
MAX_RTT_MS = 600             # Allow up to 600ms for South America, but sort by lowest ping.

# Output Files
FILES = {
    "fastest": "fastest_global.txt",
    "na": "na_us_mx.txt",
    "sa": "sa.txt",
    "uk": "uk.txt",
    "canada": "canada.txt"
}
for f in FILES.values(): Path(f).touch()

# Region Definitions
SA_COUNTRIES = {"BR", "AR", "CL", "CO", "PE", "VE", "EC", "BO", "PY", "UY"}
NA_COUNTRIES = {"US", "MX", "PA", "CR"} # Keeping CA separate as requested

# Global Config Sources
SUBSCRIPTION_URLS = [
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/all_extracted_configs.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
    "https://raw.githubusercontent.com/Turbine8845/telegram-configs-collector/main/protocols/vless",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
]

def fetch_url(url):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
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
            return {
                "host": data.get("add"), "port": int(data.get("port", 0)),
                "ps": data.get("ps", ""), "net": data.get("net", ""),
                "security": data.get("tls", ""), "is_reality": False, "link": link
            }
        if link.startswith("vless://"):
            parsed = urllib.parse.urlparse(link)
            params = urllib.parse.parse_qs(parsed.query)
            security = params.get("security", [""])[0].lower()
            return {
                "host": parsed.hostname, "port": parsed.port or 443,
                "ps": urllib.parse.unquote(parsed.fragment or ""),
                "net": params.get("type", [""])[0].lower(),
                "security": security, "is_reality": security == "reality", "link": link
            }
    except: return None

def check_connectivity_with_rtt(node):
    try:
        addr = socket.gethostbyname(node["host"])
        start = time.time()
        sock = socket.create_connection((addr, node["port"]), timeout=TCP_TIMEOUT)
        rtt = (time.time() - start) * 1000
        sock.close()
        
        if rtt > MAX_RTT_MS: return None
            
        node["rtt"] = round(rtt, 2)
        node["ip"] = addr
        return node
    except:
        return None

def batch_geoip_lookup(ips):
    results = {}
    try:
        payload = [{"query": ip, "fields": "countryCode,city,isp,query"} for ip in ips]
        r = requests.post("http://ip-api.com/batch", json=payload, timeout=15)
        for data in r.json():
            if data.get("status") != "fail":
                results[data["query"]] = (
                    data.get("countryCode", "").upper(),
                    data.get("city", ""),
                    data.get("isp", "")
                )
    except: pass
    return results

def main():
    print("=== V2RAY MULTI-REGION FETCHER (FASTEST, NA, SA, UK, CA) ===")
    
    raw_data = ""
    for url in SUBSCRIPTION_URLS:
        print(f"[*] Fetching: {url[:60]}...")
        raw = fetch_url(url)
        if raw: raw_data += raw + "\n"

    all_links = decode_sub(raw_data)
    print(f"\n[+] Total unique links found: {len(all_links)}")

    candidates = []
    for l in all_links:
        p = parse_link(l)
        if p and p["host"]: candidates.append(p)

    # Prioritize Reality nodes and regular TCP over Websocket for testing
    candidates.sort(key=lambda x: (not x["is_reality"], x["net"] == "ws"))
    candidates = candidates[:MAX_LINKS_TO_TEST]
    
    print(f"[*] Ping testing top {len(candidates)} candidates (Threads=100)...")
    working_nodes = []
    seen_ips = set()
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(check_connectivity_with_rtt, c) for c in candidates]
        for fut in as_completed(futures):
            res = fut.result()
            if res and res["ip"] not in seen_ips:
                seen_ips.add(res["ip"])
                working_nodes.append(res)

    print(f"[+] {len(working_nodes)} unique, active nodes responded.")
    print("\n[*] Batch GeoIP verification...")

    # Fetch GeoIP for all working nodes
    for i in range(0, len(working_nodes), 100):
        batch = working_nodes[i:i+100]
        geo_data = batch_geoip_lookup([n["ip"] for n in batch])
        for node in batch:
            info = geo_data.get(node["ip"], (None, "", ""))
            node["country"] = info[0]
            node["city"] = info[1]
            node["isp"] = info[2]

    # Filter out Cloudflare disguised IPs
    valid_nodes = [n for n in working_nodes if n.get("isp") and "cloudflare" not in n["isp"].lower()]

    # Sort all by ping (fastest first)
    valid_nodes.sort(key=lambda x: x["rtt"])

    # Categorize
    lists = {"fastest": [], "na": [], "sa": [], "uk": [], "canada": []}

    for n in valid_nodes:
        cc = n.get("country")
        
        # 1. Fastest Global (Top low ping nodes anywhere)
        if len(lists["fastest"]) < MAX_PER_LIST:
            lists["fastest"].append(n)
            
        # 2. North America
        if cc in NA_COUNTRIES and len(lists["na"]) < MAX_PER_LIST:
            lists["na"].append(n)
            
        # 3. South America
        if cc in SA_COUNTRIES and len(lists["sa"]) < MAX_PER_LIST:
            lists["sa"].append(n)
            
        # 4. UK
        if cc == "GB" and len(lists["uk"]) < MAX_PER_LIST:
            lists["uk"].append(n)
            
        # 5. Canada
        if cc == "CA" and len(lists["canada"]) < MAX_PER_LIST:
            lists["canada"].append(n)

    # Save and Print Summary
    print(f"\n{'='*50}")
    for key, nodes in lists.items():
        filename = FILES[key]
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(n["link"] for n in nodes))
            
        print(f"[{key.upper()}] Saved {len(nodes)} nodes -> {filename}")
        if nodes:
            avg_ping = sum(n["rtt"] for n in nodes) / len(nodes)
            print(f"      Avg Ping: {avg_ping:.1f}ms | Top Country: {nodes[0].get('country')}")
    print(f"{'='*50}\n[DONE] Successfully categorized and saved all lists.")

if __name__ == "__main__":
    main()
