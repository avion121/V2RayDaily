# Auto-run every 15 minutes (2-minute setup)

Only **you** can do steps 1 and 2 (GitHub token + cron-job.org account). Copy-paste the values below.

---

## Step 1: Create a GitHub token (~1 min)

1. Open: **https://github.com/settings/tokens/new**
2. **Note:** `V2RayDaily`
3. **Expiration:** 90 days (or No expiration)
4. **Scopes:** tick **`repo`**
5. Click **Generate token** → **copy the token** (starts with `ghp_`)

---

## Step 2: Create the cron job (~1 min)

1. Open: **https://cron-job.org** → sign up / log in (free).
2. Click **Create cronjob**.
3. Fill in:

| Field | Value (copy-paste) |
|-------|--------------------|
| **Title** | `V2RayDaily` |
| **Address (URL)** | `https://api.github.com/repos/avion121/V2RayDaily/actions/workflows/update-v2ray-config.yml/dispatches` |
| **Schedule** | Every 15 minutes (or `*/15 * * * *`) |
| **Request method** | `POST` |

4. **Request headers** (add each header):

| Name | Value |
|------|--------|
| `Authorization` | `Bearer PASTE_YOUR_TOKEN_HERE` ← replace with your token from Step 1 |
| `Accept` | `application/vnd.github+json` |
| `X-GitHub-Api-Version` | `2022-11-28` |

5. **Request body** (if there’s a body / raw body field):

```json
{"ref":"main"}
```

6. **Save** the cronjob.

Done. The workflow will run every 15 minutes automatically. Check: **https://github.com/avion121/V2RayDaily/actions**
