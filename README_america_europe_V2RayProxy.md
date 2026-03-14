# america_europe_V2RayProxy

Fetches **free** V2Ray (VMess/VLESS) configs from public subscription sources, keeps **only America and Europe** servers, tests each one, and saves **only working** nodes. Output is **sorted: America first, then UK, then rest of Europe** (one config per server, no duplicates).

## Auto-run every 5 minutes (GitHub Actions)

If this repo is on GitHub, the workflow in `.github/workflows/update-v2ray-config.yml` runs **every 5 minutes** and commits the updated list.

1. Push this repo to GitHub (including `.github/workflows/update-v2ray-config.yml`).
2. The workflow runs on schedule and on **workflow_dispatch** (manual run from the **Actions** tab).
3. After each run, **`hiddify_america_europe.txt`** is updated in the repo. Use the raw file as a subscription or copy-paste into Hiddify:
   - Raw URL: `https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/BRANCH/hiddify_america_europe.txt`  
   Replace `YOUR_USERNAME`, `YOUR_REPO`, and `BRANCH` (e.g. `main`).

## Run locally (F:\ or any directory)

1. Copy `america_europe_V2RayProxy.py` to your folder (script auto-installs `requests` if needed).

2. Open PowerShell:
   ```powershell
   cd F:\V2Ray
   python america_europe_V2RayProxy.py
   ```

3. Output is written in the **same folder**:
   - **hiddify_america_europe.txt** – one VMess/VLESS link per line (working only, sorted America → UK → rest; paste into Hiddify or use as subscription).

## What it does

- Fetches from multiple free V2Ray subscription URLs (GitHub-based public lists).
- Decodes base64 subscriptions and parses `vmess://` and `vless://` links.
- Filters to **America and Europe** by node name/remark (default; set `SKIP_GEOIP = False` for GeoIP-based filtering, which is slower).
- **Tests each node** with TCP connectivity (or real VMess/VLESS handshake if `python-v2ray` is installed).
- **Sorts output**: America first, then UK, then rest of Europe.
- **Deduplicates**: one config per server (host:port:uuid). Saves only working nodes to **hiddify_america_europe.txt**.

## Notes

- **Free**: Uses only free subscription sources. With `SKIP_GEOIP = True` (default), no GeoIP calls — filtering is by name only and very fast.
- **Strict “working” check**: If `python-v2ray` is installed (`pip install python-v2ray`), the script can run a real VMess/VLESS handshake; otherwise it uses TCP reachability.
- **Re-run to refresh**: Public nodes can go offline anytime; re-run the script or rely on the GitHub Action to refresh.
- **Hiddify**: Paste the contents of `hiddify_america_europe.txt` (or use the raw URL in GitHub) in Hiddify → Add configs / Import from clipboard.
