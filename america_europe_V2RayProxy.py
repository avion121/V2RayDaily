#!/usr/bin/env python3
from __future__ import annotations

"""
America & Europe V2Ray Proxy Fetcher
Fetches free V2Ray (VMess/VLESS) configs from public subscriptions,
filters to America and Europe only, tests with real protocol handshake when possible,
and saves only working nodes to a single file for Hiddify (copy-paste from clipboard).
Run: python america_europe_V2RayProxy.py
Output: one file (hiddify_america_europe.txt) + content copied to clipboard.
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
    print("Installing required: requests")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# Optional: copy to clipboard for Hiddify paste
try:
    import pyperclip
except ImportError:
    pyperclip = None

# Optional: real VMess/VLESS handshake testing (pip install python-v2ray)
USE_STRICT_TEST = True
_v2ray_tester = None
_v2ray_available = None

# ---------------------------------------------------------------------------
# Free V2Ray subscription URLs (VMess/VLESS) - from public repos
# ---------------------------------------------------------------------------
SUBSCRIPTION_URLS = [
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/all_configs.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/sakha1370/OpenRay/refs/heads/main/output/all_valid_proxies.txt",
    "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vl.txt",
    "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vm.txt",
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/protocols/vmess.txt",
    "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/protocols/vless.txt",
    "https://raw.githubusercontent.com/CidVpn/cid-vpn-config/refs/heads/main/general.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/all_extracted_configs.txt",
    "https://raw.githubusercontent.com/wuqb2i4f/xray-config-toolkit/main/output/base64/mix-uri",
    "https://raw.githubusercontent.com/acymz/AutoVPN/refs/heads/main/data/V2.txt",
    "https://raw.githubusercontent.com/yitong2333/proxy-minging/refs/heads/main/v2ray.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vless.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/filtered/subs/vmess.txt",
]

# GeoIP: ip-api.com free tier = 45 requests/minute. Sleep between calls to stay under limit.
# 45/60 => max 0.75 req/s => min 1.34s between requests; 1.5s is safe.
GEOIP_RATE_LIMIT = 1.5
TCP_TIMEOUT = 6
FETCH_TIMEOUT = 25
MAX_WORKERS = 8
# Timeout for real protocol test (python-v2ray) per node
STRICT_TEST_TIMEOUT_MS = 10000
# Cap links to process when using GeoIP (slow). Ignored when SKIP_GEOIP=True.
MAX_LINKS_TO_PROCESS = 8000
# Skip GeoIP lookups: filter by node name/remark only (instant). Set False for accurate but slow GeoIP.
SKIP_GEOIP = True

# America (North, Central, South) and Europe only – ISO 3166-1 alpha-2
AMERICA_CODES = {
    "AG", "AR", "BS", "BB", "BZ", "BO", "BR", "CA", "CL", "CO", "CR", "CU", "DM", "DO",
    "EC", "SV", "GD", "GT", "GY", "HT", "HN", "JM", "MX", "NI", "PA", "PY", "PE", "KN",
    "LC", "SR", "TT", "US", "UY", "VC", "VE",
}
EUROPE_CODES = {
    "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME",
    "NL", "MK", "NO", "PL", "PT", "RO", "RU", "SM", "RS", "SK", "SI", "ES", "SE", "CH",
    "UA", "GB", "VA", "TR", "XK",
}
ALLOWED_COUNTRY_CODES = AMERICA_CODES | EUROPE_CODES


def out_dir():
    return Path(__file__).resolve().parent


def _ensure_strict_tester():
    """Try to load python-v2ray and ensure binaries. Returns (tester, parse_uri) or (None, None)."""
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
    except Exception as e:
        _v2ray_available = False
        print(f"  [note] Strict test (python-v2ray) unavailable: {e}")
        print("  [note] Install with: pip install python-v2ray  (then re-run for real VMess/VLESS checks)")
        return None, None


def test_nodes_strict(links: list[str]) -> tuple[list[str], list[dict]]:
    """
    Test nodes with real VMess/VLESS handshake via python-v2ray.
    Returns (list of working links, list of result dicts with tag/ping_ms/status).
    """
    tester, parse_uri_fn = _ensure_strict_tester()
    if not tester or not parse_uri_fn:
        return [], []
    # Keep order: parsed[i] and links[i] correspond (only include parsed where parse succeeded)
    parsed = []
    valid_links = []
    for uri in links:
        try:
            p = parse_uri_fn(uri)
            if p:
                parsed.append(p)
                valid_links.append(uri)
        except Exception:
            pass
    if not parsed:
        return [], []
    try:
        results = tester.test_uris(parsed)
    except Exception as e:
        print(f"  [warn] Strict test failed: {e}")
        return [], []
    # Results are in same order as parsed; parsed[i] <-> valid_links[i]
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
        print(f"  [skip] {url[:60]}... -> {e}")
        return None


def decode_subscription(raw: str) -> list[str]:
    links = []
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
        # UUID is before @ in netloc, e.g. uuid@host:port
        netloc = parsed.netloc or ""
        uid = (netloc.split("@")[0] if "@" in netloc else "").strip()
        if not host:
            return None
        return {"type": "vless", "host": host, "port": port, "uuid": uid, "link": link, "ps": (parsed.fragment or "")}
    except Exception:
        return None


def parse_link(link: str) -> dict | None:
    return parse_vmess(link) or parse_vless(link)


def get_country(host: str, cache: dict) -> str | None:
    if host in cache:
        return cache[host]
    time.sleep(GEOIP_RATE_LIMIT)
    try:
        r = requests.get(
            f"http://ip-api.com/json/{host}?fields=countryCode,status",
            timeout=10,
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


def is_america_or_europe(country: str | None, ps: str) -> bool:
    if country and country.upper() in ALLOWED_COUNTRY_CODES:
        return True
    if country in ("UK",):  # some APIs return UK
        return True
    ps_upper = (" " + (ps or "") + " ").upper()
    # Match country names and common abbreviations in node remarks
    america_keywords = (" USA ", " US ", " UNITED STATES", " CANADA ", " MEXICO ", " BRAZIL ", " AMERICA", " NORTH ", " SOUTH ", " CA ", " MX ", " BR ")
    europe_keywords = (
        " UK ", " UNITED KINGDOM", " GERMANY", " FRANCE", " NETHERLANDS", " EUROPE", " EU ", " DE ", " FR ", " NL ", " ITALY", " SPAIN ",
        " NORDIC ", " NETHERLAND", " ROMANIA", " POLAND", " SWEDEN", " NORWAY", " FINLAND", " SWITZERLAND", " AUSTRIA", " BELGIUM ",
        " PORTUGAL", " GREECE", " TURKEY", " UKRAINE", " IRELAND", " CZECH", " HUNGARY", " BULGARIA", " CROATIA", " SERBIA ",
    )
    return any(x in ps_upper for x in america_keywords) or any(x in ps_upper for x in europe_keywords)


# Order in output: 0 = America first, 1 = UK, 2 = rest of Europe (client tries in this order)
AMERICA_COUNTRY_CODES = {"US", "CA", "MX", "BR", "AR", "CL", "CO", "PE", "VE", "EC", "GT", "CU", "HT", "DO", "HN", "JM", "PA", "PY", "UY", "CR", "BO", "SV", "NI", "BS", "BB", "BZ", "DM", "GD", "GY", "SR", "TT", "VC", "AG"}
UK_COUNTRY_CODES = {"GB", "UK"}


def region_priority(node: dict) -> int:
    """0 = America (first), 1 = UK, 2 = rest of Europe."""
    country = (node.get("country") or "").upper()
    ps = " " + (node.get("ps") or "") + " "
    ps_upper = ps.upper()
    if country in AMERICA_COUNTRY_CODES:
        return 0
    if country in UK_COUNTRY_CODES:
        return 1
    if " USA " in ps_upper or " US " in ps_upper or " UNITED STATES" in ps_upper or " CANADA " in ps_upper or " AMERICA" in ps_upper or " CA " in ps_upper or " MX " in ps_upper or " BRAZIL " in ps_upper:
        return 0
    if " UK " in ps_upper or " UNITED KINGDOM" in ps_upper:
        return 1
    return 2


def test_tcp(host: str, port: int) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=TCP_TIMEOUT)
        sock.close()
        return True
    except (socket.timeout, OSError, socket.gaierror):
        return False


def main():
    print("America & Europe V2Ray Proxy – single file for Hiddify (clipboard paste).\n")
    base = out_dir()
    print(f"Output directory: {base}\n")

    # 1) Fetch all subscriptions
    all_links = []
    for url in SUBSCRIPTION_URLS:
        print(f"Fetching: {url[:70]}...")
        raw = fetch_url(url)
        if raw:
            links = decode_subscription(raw)
            all_links.extend(links)
    all_links = list(dict.fromkeys(all_links))
    print(f"\nTotal unique VMess/VLESS links: {len(all_links)}")
    max_links = MAX_LINKS_TO_PROCESS if not SKIP_GEOIP else min(len(all_links), 20000)
    if len(all_links) > max_links:
        all_links = all_links[:max_links]
        print(f"Capping to first {max_links} links.")

    if not all_links:
        print("No links found. Check internet or subscription URLs.")
        return

    # 2) Parse and filter by America & Europe (by name/remark only when SKIP_GEOIP, else GeoIP)
    if SKIP_GEOIP:
        print("Filtering by region (America/Europe) using node names only (fast)...")
    else:
        print("Filtering by region (America/Europe)... GeoIP lookups are rate-limited, this may take a while.")
    nodes = []
    geo_cache = {} if not SKIP_GEOIP else None
    total = len(all_links)
    for i, link in enumerate(all_links):
        if not SKIP_GEOIP and ((i + 1) % 500 == 0 or i == 0):
            print(f"  Progress: {i + 1}/{total} links, {len(geo_cache)} hosts looked up, {len(nodes)} America/Europe so far...")
        node = parse_link(link)
        if not node:
            continue
        country = None if SKIP_GEOIP else get_country(node["host"], geo_cache)
        if is_america_or_europe(country, node["ps"]):
            node["country"] = country or "?"
            nodes.append(node)
    if SKIP_GEOIP and total > 1000:
        print(f"  Processed {total} links.")
    print(f"After America & Europe filter: {len(nodes)} nodes")

    if not nodes:
        print("No America/Europe nodes found. Try again later or add more subscription URLs.")
        return

    # 3) Test: prefer real VMess/VLESS handshake (python-v2ray); fallback to TCP
    working = []
    links_only_for_test = [n["link"] for n in nodes]

    if USE_STRICT_TEST:
        print("\nTrying strict test (real VMess/VLESS handshake via python-v2ray)...")
        working_links, strict_results = test_nodes_strict(links_only_for_test)
        if working_links:
            working = [n for n in nodes if n["link"] in working_links]
            for r in (strict_results or []):
                if r.get("status") == "success":
                    print(f"  [OK] {r.get('tag', '')[:40]}... | Latency: {r.get('ping_ms', -1)} ms")
        if not working and strict_results is not None:
            print("  No nodes passed strict test (auth/blocked/down). Falling back to TCP check...")

    if not working:
        print("\nTesting TCP connectivity (server reachable)...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_tcp, n["host"], n["port"]): n for n in nodes}
            for i, fut in enumerate(as_completed(futures)):
                node = futures[fut]
                try:
                    if fut.result():
                        working.append(node)
                        print(f"  [OK] {node['host']}:{node['port']} ({node.get('country', '?')})")
                except Exception:
                    pass
                if (i + 1) % 20 == 0:
                    print(f"  Tested {i + 1}/{len(nodes)}...")

    print(f"\nWorking America & Europe V2Ray nodes: {len(working)}")

    if not working:
        print("No working nodes. Run again later or install python-v2ray for stricter checks: pip install python-v2ray")
        return

    # 4) Order: America first, then UK, then rest of Europe (default connection order for Hiddify)
    working.sort(key=region_priority)
    n_america = sum(1 for n in working if region_priority(n) == 0)
    n_uk = sum(1 for n in working if region_priority(n) == 1)
    n_rest = len(working) - n_america - n_uk
    print(f"  Order: America {n_america}, UK {n_uk}, rest {n_rest}")

    # 5) One config per server (host:port:uuid) – only running nodes, no duplicates
    seen_key: dict[tuple[str, int, str], str] = {}
    for n in working:
        key = (n["host"], n["port"], n.get("uuid") or "")
        if key not in seen_key:
            seen_key[key] = n["link"]
    links_only = list(seen_key.values())
    print(f"Unique nodes (one per server): {len(links_only)}")
    content = "\n".join(links_only)
    out_file = base / "hiddify_america_europe.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\nSaved single file: {out_file}")

    # Copy to clipboard for Hiddify paste (skip in CI e.g. GitHub Actions)
    in_ci = os.environ.get("CI") == "true"
    if not in_ci and pyperclip:
        try:
            pyperclip.copy(content)
            print("Copied to clipboard. Paste in Hiddify (Add configs / Import from clipboard).")
        except Exception as e:
            print(f"Clipboard copy failed: {e}. Open the file and copy manually.")
    elif not in_ci:
        print("Install pyperclip for auto clipboard copy: pip install pyperclip")
        print("Or open hiddify_america_europe.txt, Ctrl+A, Ctrl+C, then paste in Hiddify.")

    print("\nDone. In Hiddify: paste from clipboard or import the file.")
    print("Public nodes can go offline anytime; re-run this script to refresh.")


if __name__ == "__main__":
    main()
