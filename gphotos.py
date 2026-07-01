"""Minimal Google Photos client using the append-only API.

The broad Google Photos scopes were removed on 2025-03-31, but
`photoslibrary.appendonly` still allows: create an album, upload media
bytes, and add those uploads to the app-created album. That is exactly
this workflow, and all we need here.

Auth is a plain refresh-token -> access-token exchange, so the only
runtime dependency is `requests`.
"""

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://photoslibrary.googleapis.com/v1"
UPLOAD_URL = API + "/uploads"


class GooglePhotos:
    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.session = requests.Session()
        self._access_token = None

    def _token(self):
        if self._access_token is None:
            resp = self.session.post(TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }, timeout=30)
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
        return self._access_token

    def _headers(self, extra=None):
        h = {"Authorization": f"Bearer {self._token()}"}
        if extra:
            h.update(extra)
        return h

    def create_album(self, title):
        resp = self.session.post(
            f"{API}/albums", headers=self._headers(),
            json={"album": {"title": title}}, timeout=30)
        resp.raise_for_status()
        return resp.json()["id"]

    def upload_bytes(self, data, filename):
        """Upload raw bytes; returns an upload token to hand to batch_create."""
        resp = self.session.post(UPLOAD_URL, headers=self._headers({
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": "image/jpeg",
            "X-Goog-Upload-Protocol": "raw",
            "X-Goog-Upload-File-Name": filename,
        }), data=data, timeout=120)
        resp.raise_for_status()
        return resp.text

    def batch_create(self, album_id, items):
        """items: list of (upload_token, description). Max 50 per call.

        Returns the list of newMediaItemResults so the caller can tell which
        uploads actually became media items.
        """
        new_media_items = [{
            "description": desc or "",
            "simpleMediaItem": {"uploadToken": token},
        } for token, desc in items]
        resp = self.session.post(
            f"{API}/mediaItems:batchCreate", headers=self._headers(),
            json={"albumId": album_id, "newMediaItems": new_media_items}, timeout=60)
        resp.raise_for_status()
        return resp.json().get("newMediaItemResults", [])
