#!/usr/bin/env python3
import base64, json, socket, subprocess, sys, time, urllib.parse, html, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# --- AUTO INSTALL REQUESTS ---
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# --- CONFIGURATION ---
MAX_LINKS_TO_TEST = 4000
MAX_PER_LIST = 100
TCP_TIMEOUT = 2.5
MAX_RTT_MS = 600

# Output Files
FILES = {
    "fastest": "fastest_global.txt",
    "na": "na_us_mx.txt",
    "sa": "sa.txt",
    "uk": "uk.txt",
    "canada": "canada.txt"
}
for f in FILES.values(): Path(f).touch()

SA_COUNTRIES = {"BR", "AR", "CL", "CO", "PE", "VE", "EC", "BO", "PY", "UY"}
NA_COUNTRIES = {"US", "MX", "PA", "CR"}

SUBSCRIPTION_URLS =[
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
    if not raw: return[]
    for chunk in raw.split():
        try:
            decoded = base64.b64decode(chunk + "==").decode("utf-8", errors="ignore")
            for line in decoded.splitlines():
                if line.startswith(("vmess://", "vless://")): links.append(line.strip())
        except: pass
    for line in raw.splitlines():
        if line.startswith(("vmess://", "vless://")): links.append(line.strip())
    return list(set(links))

def has_garbage(text):
    """Detects emojis, broken brackets, and placeholder garbage that crashes Hiddify"""
    if not text: return False
    # If any of these are in the SNI, Host, or Path, it's a corrupted link.
    garbage_chars = ["🔒", "[", "]", "{", "}", " ", "EbraSha", "extra="]
    return any(c in text for c in garbage_chars)

def parse_link(link):
    try:
        # FIX 1: Unescape broken HTML ampersands (e.g., &amp;security= -> &security=)
        link = html.unescape(link).replace("&amp;", "&")

        if link.startswith("vmess://"):
            data = json.loads(base64.b64decode(link[8:] + "==").decode("utf-8"))
            
            # FIX 2: Strict Garbage Filtering
            if has_garbage(str(data.get("sni", ""))) or has_garbage(str(data.get("host", ""))):
                return None
            if not data.get("add") or not str(data.get("port", "")).isdigit():
                return None

            return {
                "host": data.get("add"), "port": int(data.get("port", 0)),
                "ps": data.get("ps", ""), "net": data.get("net", ""),
                "security": data.get("tls", ""), "is_reality": False, "link": link
            }
            
        if link.startswith("vless://"):
            parsed = urllib.parse.urlparse(link)
            params = urllib.parse.parse_qs(parsed.query)
            
            security = params.get("security", [""])[0].lower()
            sni = params.get("sni", [""])[0]
            path = params.get("path", [""])[0]
            flow = params.get("flow", [""])[0]
            
            # FIX 3: Catch broken VLESS configurations
            if not parsed.hostname or not str(parsed.port).isdigit(): return None
            if has_garbage(sni) or has_garbage(path) or has_garbage(urllib.parse.unquote(link)): return None
            # Catch "security=" empty string errors
            if security == "" and "security=" in link: return None
            if flow == "" and "flow=" in link: return None

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
        payload =[{"query": ip, "fields": "countryCode,city,isp,query"} for ip in ips]
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
    print("=== V2RAY MULTI-REGION FETCHER (STRICT SANITIZATION) ===")
    
    raw_data = ""
    for url in SUBSCRIPTION_URLS:
        print(f"[*] Fetching: {url[:60]}...")
        raw = fetch_url(url)
        if raw: raw_data += raw + "\n"

    all_links = decode_sub(raw_data)
    print(f"\n[+] Total unique links found: {len(all_links)}")

    candidates =[]
    for l in all_links:
        p = parse_link(l)
        if p and p["host"]: candidates.append(p)

    candidates.sort(key=lambda x: (not x["is_reality"], x["net"] == "ws"))
    candidates = candidates[:MAX_LINKS_TO_TEST]
    
    print(f"[*] Clean candidates surviving strict filter: {len(candidates)}")
    print(f"[*] Ping testing top {len(candidates)} candidates (Threads=100)...")
    working_nodes =[]
    seen_ips = set()
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures =[executor.submit(check_connectivity_with_rtt, c) for c in candidates]
        for fut in as_completed(futures):
            res = fut.result()
            if res and res["ip"] not in seen_ips:
                seen_ips.add(res["ip"])
                working_nodes.append(res)

    print(f"[+] {len(working_nodes)} unique, active nodes responded.")
    print("\n[*] Batch GeoIP verification...")

    for i in range(0, len(working_nodes), 100):
        batch = working_nodes[i:i+100]
        geo_data = batch_geoip_lookup([n["ip"] for n in batch])
        for node in batch:
            info = geo_data.get(node["ip"], (None, "", ""))
            node["country"] = info[0]
            node["city"] = info[1]
            node["isp"] = info[2]

    valid_nodes =[n for n in working_nodes if n.get("isp") and "cloudflare" not in n["isp"].lower()]
    valid_nodes.sort(key=lambda x: x["rtt"])

    lists = {"fastest": [], "na":[], "sa": [], "uk": [], "canada":[]}

    for n in valid_nodes:
        cc = n.get("country")
        if len(lists["fastest"]) < MAX_PER_LIST: lists["fastest"].append(n)
        if cc in NA_COUNTRIES and len(lists["na"]) < MAX_PER_LIST: lists["na"].append(n)
        if cc in SA_COUNTRIES and len(lists["sa"]) < MAX_PER_LIST: lists["sa"].append(n)
        if cc == "GB" and len(lists["uk"]) < MAX_PER_LIST: lists["uk"].append(n)
        if cc == "CA" and len(lists["canada"]) < MAX_PER_LIST: lists["canada"].append(n)

    print(f"\n{'='*50}")
    for key, nodes in lists.items():
        filename = FILES[key]
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(n["link"] for n in nodes))
            
        print(f"[{key.upper()}] Saved {len(nodes)} clean nodes -> {filename}")
        if nodes:
            avg_ping = sum(n["rtt"] for n in nodes) / len(nodes)
            print(f"      Avg Ping: {avg_ping:.1f}ms | Top Country: {nodes[0].get('country')}")
    print(f"{'='*50}\n[DONE] Successfully sanitized, categorized and saved all lists.")

if __name__ == "__main__":
    main()
