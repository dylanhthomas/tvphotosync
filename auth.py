"""One-time helper to mint a Google refresh token.

Run locally once, in a browser-capable environment:

    GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python auth.py

It opens a browser, you grant consent for your own Google account, and it
prints a refresh token. Store that as the GOOGLE_REFRESH_TOKEN secret.

Requires the OAuth app to be published "In production" (see README) so the
refresh token does not expire after 7 days.
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/photoslibrary.appendonly"]


def main():
    config = {
        "installed": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        raise SystemExit(
            "No refresh token returned. Revoke the app's access at "
            "https://myaccount.google.com/permissions and try again.")
    print("\n=== GOOGLE_REFRESH_TOKEN ===")
    print(creds.refresh_token)


if __name__ == "__main__":
    main()
