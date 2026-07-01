"""Client for reading a *public* iCloud Shared Album.

An iOS Shared Album with "Public Website" enabled is backed by two
unofficial-but-stable JSON endpoints. No Apple login is required.

  webstream    -> list of photos (each with a photoGuid and size "derivatives")
  webasseturls -> short-lived download URLs, keyed by each derivative's checksum

The host is partitioned ("p<NN>-sharedstreams.icloud.com"). The correct
partition is derived from the album token, and the first request may still
return HTTP 330 pointing at a different host, which we follow once.
"""

import requests

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _base62(s):
    n = 0
    for ch in s:
        n = n * 62 + _ALPHABET.index(ch)
    return n


def _base_url(token, host=None):
    if host is None:
        # First char 'A' => partition is the next char; otherwise the next two.
        if token[0] == "A":
            partition = _base62(token[1])
        else:
            partition = _base62(token[1:3])
        host = f"p{partition}-sharedstreams.icloud.com"
    return f"https://{host}/{token}/sharedstreams/"


class SharedAlbum:
    def __init__(self, token, session=None):
        self.token = token
        self.session = session or requests.Session()
        self.base_url = _base_url(token)

    def _post(self, endpoint, payload):
        resp = self.session.post(self.base_url + endpoint, json=payload, timeout=30)
        # Partition redirect: retry once against the host Apple tells us to use.
        if resp.status_code == 330:
            host = resp.json().get("X-Apple-MMe-Host")
            if host:
                self.base_url = _base_url(self.token, host=host)
                resp = self.session.post(self.base_url + endpoint, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_photos(self):
        """Return the raw photo objects in the album."""
        return self._post("webstream", {"streamCtag": None}).get("photos", [])

    def get_asset_urls(self, photo_guids):
        """Map each derivative checksum -> {url_location, url_path} for the given photos."""
        items = {}
        for i in range(0, len(photo_guids), 25):
            chunk = photo_guids[i:i + 25]
            data = self._post("webasseturls", {"photoGuids": chunk})
            items.update(data.get("items", {}))
        return items


def best_derivative(photo):
    """Pick the highest-resolution downloadable derivative of a photo."""
    best = None
    for d in photo.get("derivatives", {}).values():
        if not d.get("checksum"):
            continue
        if best is None or int(d.get("fileSize") or 0) > int(best.get("fileSize") or 0):
            best = d
    return best


def asset_url(item):
    return f"https://{item['url_location']}{item['url_path']}"


if __name__ == "__main__":
    # Verification helper: python icloud.py <ALBUM_TOKEN>
    import sys

    album = SharedAlbum(sys.argv[1])
    photos = album.get_photos()
    print(f"{len(photos)} item(s) in album")
    guids = [p["photoGuid"] for p in photos if p.get("mediaAssetType") != "video"]
    urls = album.get_asset_urls(guids)
    for p in photos[:5]:
        d = best_derivative(p)
        got = "yes" if d and d["checksum"] in urls else "no"
        print(f"  {p['photoGuid']}  type={p.get('mediaAssetType', 'image')}  url={got}")
