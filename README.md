# tvphotosync

Mirror photos from an **iOS Shared Album** into a **Google Photos album** so they
show up on a **Google TV** ambient-mode screensaver.

Your family already drops photos into an iOS Shared Album — this keeps a Google
Photos album in sync with it automatically. It runs free in the cloud on GitHub
Actions (or locally), polling the shared album every ~20 minutes and uploading
anything new.

## Why this exists

The Google TV screensaver can only show photos that live in an album, and all
albums must be in one Google account. The obvious "when a photo is added to my
iOS shared album, copy it to a Google album" recipe used to be doable with
IFTTT / Make.com — but on **2025-03-31 Google removed the broad Photos API
scopes** those platforms relied on, so the Google-album step stopped working.

The narrower `photoslibrary.appendonly` scope still works: an app can create an
album, upload photos, and add them to that album. This repo is a ~150-line
purpose-built script that does exactly that and nothing more.

## How it works

```
iOS Shared Album --(Public Website)--> iCloud public JSON API
                                              |
                                   sync.py (every ~20 min via GitHub Actions)
                                     - list photos, diff against state.json
                                     - download new ones (largest size)
                                     - upload to Google Photos + add to album
                                     - record synced photo IDs in state.json
                                              |
                                   Google Photos album  -->  Google TV screensaver
```

## One-time setup

### 1. iCloud shared album
1. In the Photos app, open (or create) the shared album your family uses.
2. Album settings → enable **Public Website**.
3. Copy the link. It looks like `https://www.icloud.com/sharedalbum/#B0aBcDeFg...`.
   The part **after `#`** is your `ICLOUD_ALBUM_TOKEN`.

### 2. Google Cloud project (free)
1. Go to <https://console.cloud.google.com/> → create a project.
2. **APIs & Services → Library →** enable **Photos Library API**.
3. **OAuth consent screen:** User type **External**. Add the scope
   `https://www.googleapis.com/auth/photoslibrary.appendonly`. Add your Google
   account as a test user.
4. **Publish app → In production** and accept the "unverified app" warning.
   ⚠️ This matters: while the app is in *Testing*, Google revokes the refresh
   token after 7 days. In production it does not expire (as long as it's used at
   least every 6 months).
5. **Credentials → Create credentials → OAuth client ID → Desktop app.** Note the
   **client ID** and **client secret**.

### 3. Mint a refresh token (run once, locally)
On a computer with a browser:
```bash
pip install -r requirements.txt
GOOGLE_CLIENT_ID=xxx GOOGLE_CLIENT_SECRET=yyy python auth.py
```
Grant consent in the browser; it prints your `GOOGLE_REFRESH_TOKEN`.

### 4. Add GitHub secrets
In this repo: **Settings → Secrets and variables → Actions → Secrets**, add:
- `ICLOUD_ALBUM_TOKEN`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

Optional **variable** (not secret) `GOOGLE_ALBUM_TITLE` to name the album
(default: `Family TV`).

### 5. Point the TV at the album
Run the workflow once (**Actions → Sync iCloud album to Google Photos → Run
workflow**) so the album gets created and populated. Then on the Google TV:
**Settings → System → Ambient mode → Google Photos →** select the album.

## Running locally instead of / alongside Actions

The same script runs anywhere:
```bash
pip install -r requirements.txt
export ICLOUD_ALBUM_TOKEN=... GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... GOOGLE_REFRESH_TOKEN=...
python sync.py
```
`state.json` tracks what's already been synced, so re-running is safe and only
uploads new photos. To run on a schedule locally, add it to cron/launchd.

## Notes & limits

- **Schedule drift:** GitHub's cron can be delayed 10–30 min — fine for a
  screensaver.
- **Auto-disable:** GitHub disables scheduled workflows after 60 days of no repo
  activity. Each run commits `state.json` when something changed, which counts as
  activity. If it ever pauses, re-enable it with one click in the Actions tab.
- **Stills only:** videos and Live Photo movies are skipped.
- **iCloud endpoints are unofficial:** if Apple changes them, the fix is isolated
  to `icloud.py`.

## Files

| File | Purpose |
| --- | --- |
| `sync.py` | Main job: diff iCloud album, upload new photos to Google Photos |
| `icloud.py` | Read a public iCloud shared album |
| `gphotos.py` | Google Photos append-only client |
| `auth.py` | One-time helper to obtain the Google refresh token |
| `state.json` | Album id + already-synced photo ids (updated by each run) |
| `.github/workflows/sync.yml` | Scheduled run + commits state back |
