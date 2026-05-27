#!/usr/bin/env python3
"""Fetch a CyberArk Identity OAuth2 client_credentials access token."""

import os
import sys
import requests
from urllib.parse import urlparse, urlunparse

# IDIRA_IDENTITY_URL points to the IDIRA REST API (…/api/idadmin).
IDENTITY_URL = os.environ["IDIRA_IDENTITY_URL"]
CLIENT_ID     = os.environ["IDIRA_ADMIN_USER"]
CLIENT_SECRET = os.environ["IDIRA_ADMIN_PWD"]


def get_auth_token() -> str:
    resp = requests.post(
        f"{IDENTITY_URL}/oauth2/platformtoken",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type":    "client_credentials",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    if resp.status_code != 200:
        # Print to stderr so the error is never captured as the token value.
        print(
            {"message": f"Failed to authenticate service account {CLIENT_ID}.",
             "http_code": resp.status_code,
             "response": resp.text},
            file=sys.stderr,
        )
        sys.exit(1)
    return resp.json()["access_token"]


if __name__ == "__main__":
    print(get_auth_token())
