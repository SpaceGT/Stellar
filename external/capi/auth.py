"""Helps authenticating with the Frontier Companion API"""

import base64
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
from urllib import parse

from aiohttp import ClientSession

from settings import CAPI

_TIMEOUT = 60
_URL = "https://auth.frontierstore.net"

_LOGGER = logging.getLogger(__name__)


class RefreshFail(Exception):
    """Raised when a token cannot be refreshed."""


class GetEndpoint(StrEnum):
    DECODE = "decode"
    ME = "me"


class PostEndpoint(StrEnum):
    TOKEN = "token"


async def _post_request(
    endpoint: PostEndpoint, query: dict[str, str], headers: dict[str, str]
) -> dict[str, Any]:
    url = f"{_URL}/{endpoint}"
    async with (
        ClientSession() as session,
        session.post(
            url, data=parse.urlencode(query), headers=headers, timeout=_TIMEOUT
        ) as response,
    ):
        if response.status == 401:
            raise RefreshFail

        response.raise_for_status()
        data: dict[str, str | int] = await response.json()

    return data


async def _get_request(
    endpoint: GetEndpoint, headers: dict[str, str]
) -> dict[str, Any]:
    url = f"{_URL}/{endpoint}"
    async with (
        ClientSession(raise_for_status=True) as session,
        session.get(url, headers=headers, timeout=_TIMEOUT) as response,
    ):
        data: dict[str, str | int] = await response.json()

    return data


async def request(endpoint: GetEndpoint, access_token: str) -> dict[str, Any]:
    """
    Query a given endpoint and return raw JSON.
    Requires an access token - use existing functions for authentication.
    """

    headers = {
        "User-Agent": CAPI.user_agent,
        "Authorization": f"Bearer {access_token}",
    }
    return await _get_request(endpoint, headers)


def _encode(data: bytes) -> str:
    string = base64.urlsafe_b64encode(data)
    text = string.decode("utf-8")
    return text.rstrip("=")


def oauth_data() -> dict[str, str]:
    """Generate data needed to authenticate your application."""
    _LOGGER.debug("Generating OAuth data")
    seed = base64.urlsafe_b64encode(os.urandom(32))

    verifier = seed.decode("utf-8")
    challenge = _encode(hashlib.sha256(seed).digest())
    state = _encode(os.urandom(32))

    audience = ["frontier", "steam"]
    if CAPI.use_epic:
        audience.append("epic")

    query = {
        "audience": ",".join(audience),
        "scope": "auth capi",
        "response_type": "code",
        "client_id": CAPI.client_id,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "redirect_uri": CAPI.redirect_url,
    }

    params = parse.urlencode(query, quote_via=parse.quote)
    return {"url": f"{_URL}/auth?{params}", "verifier": verifier, "state": state}


def get_auth_code(oauth_url: str) -> str | None:
    """Extract the auth_code from an oauth redirect URL"""

    unescaped = parse.unquote(oauth_url)
    query = parse.urlparse(unescaped).query
    queries = parse.parse_qs(query)

    return queries["code"][0] if "code" in queries else None


async def get_new_tokens(auth_code: str, verifier: str) -> tuple[str, str, datetime]:
    """Gets access tokens from an auth code and verifier."""

    headers = {
        "User-Agent": CAPI.user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    query = {
        "redirect_uri": CAPI.redirect_url,
        "code": auth_code,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
        "client_id": CAPI.client_id,
    }

    data = await _post_request(PostEndpoint.TOKEN, query, headers)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    _LOGGER.info("Fetched access tokens")
    return data["access_token"], data["refresh_token"], expiry


async def get_refreshed_tokens(refresh_token: str) -> tuple[str, str, datetime]:
    """Refreshes access tokens using a refresh token."""

    headers = {
        "User-Agent": CAPI.user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    query = {
        "grant_type": "refresh_token",
        "client_id": CAPI.client_id,
        "refresh_token": refresh_token,
    }

    data = await _post_request(PostEndpoint.TOKEN, query, headers)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

    _LOGGER.debug("Refreshed access tokens")
    return data["access_token"], data["refresh_token"], expiry


async def decode_token(access_token: str) -> tuple[int, str | None]:
    """Gets account into from an access token."""
    _LOGGER.info("Decoding access token ending in '%s'", access_token[-20:])

    data = await request(GetEndpoint.DECODE, access_token)
    assert isinstance(data["usr"], dict)
    return (int(data["usr"]["customer_id"]), data["usr"].get("thirdPartyUserId", None))
