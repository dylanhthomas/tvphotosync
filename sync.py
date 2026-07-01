"""Mirror new photos from a public iCloud Shared Album into a Google Photos album.

Idempotent: already-synced photos are tracked by iCloud photoGuid in
state.json, so re-running only uploads what is new. Videos / Live Photo
movies are skipped (a TV screensaver shows stills).

Required environment variables:
    ICLOUD_ALBUM_TOKEN      token after '#' in the public shared-album link
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REFRESH_TOKEN
Optional:
    GOOGLE_ALBUM_TITLE      target album name (default "Family TV")
    STATE_FILE              path to state file (default "state.json")
"""

import json
import os

import requests

from gphotos import GooglePhotos
from icloud import SharedAlbum, asset_url, best_derivative

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
ALBUM_TITLE = os.environ.get("GOOGLE_ALBUM_TITLE") or "Family TV"


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def main():
    gp = GooglePhotos(
        os.environ["GOOGLE_CLIENT_ID"],
        os.environ["GOOGLE_CLIENT_SECRET"],
        os.environ["GOOGLE_REFRESH_TOKEN"],
    )
    state = load_state()
    synced = set(state.get("synced_guids", []))

    album = SharedAlbum(os.environ["ICLOUD_ALBUM_TOKEN"])
    photos = album.get_photos()
    new_photos = [
        p for p in photos
        if p.get("photoGuid") not in synced and p.get("mediaAssetType") != "video"
    ]
    print(f"iCloud album: {len(photos)} item(s), {len(new_photos)} new to sync")
    if not new_photos:
        return

    album_id = state.get("google_album_id")
    if not album_id:
        album_id = gp.create_album(ALBUM_TITLE)
        state["google_album_id"] = album_id
        save_state(state)  # persist the album id even if a later step fails
        print(f"Created Google Photos album '{ALBUM_TITLE}' ({album_id})")

    urls = album.get_asset_urls([p["photoGuid"] for p in new_photos])

    pending = []  # (upload_token, description, guid)
    for p in new_photos:
        guid = p["photoGuid"]
        deriv = best_derivative(p)
        item = urls.get(deriv["checksum"]) if deriv else None
        if not item:
            print(f"  skip {guid}: no downloadable asset")
            continue
        try:
            data = requests.get(asset_url(item), timeout=120).content
            token = gp.upload_bytes(data, f"{guid}.jpg")
        except Exception as e:  # noqa: BLE001 - keep going on a single bad photo
            print(f"  skip {guid}: {e}")
            continue
        pending.append((token, p.get("caption") or "", guid))

    added = []
    for i in range(0, len(pending), 50):
        chunk = pending[i:i + 50]
        results = gp.batch_create(album_id, [(t, d) for t, d, _ in chunk])
        for (_, _, guid), res in zip(chunk, results):
            if res.get("mediaItem"):
                added.append(guid)
            else:
                print(f"  batchCreate failed {guid}: {res.get('status')}")

    if added:
        synced.update(added)
        state["synced_guids"] = sorted(synced)
        save_state(state)
    print(f"Synced {len(added)} new photo(s) to Google Photos.")


if __name__ == "__main__":
    main()
