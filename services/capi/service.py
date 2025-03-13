"""Communicates with the Companion API."""

import asyncio
import logging
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone

from aiohttp import ClientResponseError

from common import CapiData, Good
from common.enums import Service, State
from external.capi import CapiFail, EpicFail, auth, query
from storage import capi
from utils.events import AsyncEvent

_LOGGER = logging.getLogger(__name__)


class _Data:
    def __init__(self, data: Iterable[CapiData]) -> None:
        self._data: set[CapiData] = set(data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[CapiData]:
        return iter(self._data)

    def add(self, data: CapiData) -> None:
        """Add a new entry to the collection."""
        self._data.add(data)

    def find_carrier(self, callsign: str) -> CapiData | None:
        """Get CAPI information for a carrier."""
        return next((data for data in self._data if data.carrier == callsign), None)

    def find_commander(self, commander: str) -> CapiData | None:
        """Get CAPI information for a commander."""
        return next((data for data in self._data if data.commander == commander), None)

    def find_account(self, account: int) -> CapiData | None:
        """Get CAPI information for an account."""
        return next((data for data in self._data if data.customer_id == account), None)


class CapiService:
    """Communicates with the Companion API."""

    def __init__(self) -> None:
        self._data = _Data([])
        self.sync = AsyncEvent()

    async def pull(self, lazy: bool = False) -> None:
        """Fetch the latest CAPI data."""
        self._data = _Data(await capi.load_data(lazy))
        _LOGGER.debug("Pulled CAPI data")

    async def push(self) -> None:
        """Store the current CAPI data."""
        await capi.push_data(self._data)
        _LOGGER.debug("Pushed CAPI data")

    def get_carriers(self) -> list[str]:
        """Get all carriers registered with CAPI."""
        return [data.carrier for data in self._data if data.carrier]

    def get_state(self, callsign: str) -> State:
        """Gets the CAPI state for a carrier."""
        data = self._data.find_carrier(callsign)

        if not data:
            return State.UNLISTED

        if not data.access_token:
            return State.EXPIRED

        return State.SYNCING

    async def update(self, delay: timedelta = timedelta(seconds=5)) -> None:
        """Attempts to refresh all expired tokens and checks for carrier changes."""

        _LOGGER.info("Attemping CAPI update")
        for data in self._data:
            if data.access_token and data.carrier:
                continue

            if not data.access_token:
                success = await self._refresh_token(data.customer_id, lazy=True)
                await asyncio.sleep(delay.total_seconds() / 1000)

                if not success:
                    continue

            assert data.access_token

            if not data.carrier:
                try:
                    response = await query.fleetcarrier(data.access_token[0])

                except EpicFail:
                    data.access_token = None
                    _LOGGER.warning(
                        "Epic authentication failed for '%s'", data.commander
                    )

                else:
                    if response:
                        _LOGGER.info(
                            "'%s' has new carrier '%s'", data.commander, response[0][0]
                        )
                        data.carrier = response[0][0]

            await asyncio.sleep(delay.total_seconds() / 1000)

        _LOGGER.info("Finished CAPI update")
        await self.push()

    async def _refresh_token(self, account: int, lazy: bool = False) -> bool:
        """
        Refreshes a token for an account.
        Returns true on success or false if a reauth is needed.
        """

        info = self._data.find_account(account)
        if not info:
            raise ValueError(f"No account with id {account}")

        try:
            access_token, refresh_token, expiry = await auth.get_refreshed_tokens(
                info.refresh_token
            )

        except ClientResponseError:
            _LOGGER.warning("Failed to refresh CAPI token for '%s'", info.commander)
            info.access_token = None
            success = False

        else:
            _LOGGER.info("Refreshed CAPI tokens for '%s'", info.commander)
            info.access_token = (access_token, expiry)
            info.refresh_token = refresh_token
            success = True

        if not lazy:
            await self.push()

        return success

    def get_data(self) -> _Data:
        """
        Returns all Companion API data for external use.
        You should use the service directly where possible.
        """
        return self._data

    async def get_token(self, commander: str) -> tuple[str, datetime] | None:
        """
        Fetches the current access token of a commander for external use.
        You should use the service directly where possible.
        """
        info = self._data.find_commander(commander)

        if not info or not info.access_token:
            return None

        if info.access_token[1] < datetime.now(timezone.utc):
            if not await self._refresh_token(info.customer_id):
                return None

        return info.access_token

    async def auth_account(
        self, auth_code: str, verifier: str, discord: int, sync: bool = False
    ) -> bool:
        """
        Fetch and store tokens for a newly-authenticated account.
        Optionally performs an initial sync of the updated information.
        """
        delay = timedelta(seconds=1)

        try:
            access_token, refresh_token, expiry = await auth.get_new_tokens(
                auth_code, verifier
            )
        except ClientResponseError:
            _LOGGER.exception("Authentication failed!")
            return False

        await asyncio.sleep(delay.total_seconds())
        customer_id, service_id = await auth.decode_token(access_token)

        try:
            await asyncio.sleep(delay.total_seconds())
            commander = await query.profile(access_token)

            await asyncio.sleep(delay.total_seconds())
            response = await query.fleetcarrier(access_token)

        except EpicFail:
            _LOGGER.warning("Authentication failed due to Epic")
            return False

        except CapiFail:
            _LOGGER.warning("Authentication failed due to cAPI")
            return False

        if response:
            if sync:
                await self.sync.fire(
                    name=(response[0][0], response[0][1]),
                    market_id=response[0][2],
                    market=response[1],
                    system=response[2],
                )

            callsign = response[0][0]
        else:
            callsign = None

        if service_id is None:
            auth_type = Service.FRONTIER
        elif service_id.isdigit():
            auth_type = Service.STEAM
        else:
            auth_type = Service.EPIC

        data = self._data.find_account(customer_id)

        if data:
            data.auth_type = auth_type
            data.commander = commander
            data.carrier = callsign
            data.discord_id = discord
            data.access_token = (access_token, expiry)
            data.refresh_token = refresh_token

        else:
            data = CapiData(
                customer_id=customer_id,
                auth_type=auth_type,
                commander=commander,
                carrier=callsign,
                discord_id=discord,
                access_token=(access_token, expiry),
                refresh_token=refresh_token,
            )
            self._data.add(data)

        await self.push()
        return True

    async def fleetcarrier(
        self, callsign: str, lazy: bool = False
    ) -> tuple[tuple[str, str, int], list[Good], str] | None:
        """
        Get the (callsign, name, market_id), market and system of a carrier from CAPI.
        Returns None if the carrier cannot be accessed.
        """

        info = self._data.find_carrier(callsign)
        if not info or not info.access_token:
            return None

        if info.access_token[1] < datetime.now(timezone.utc):
            if not await self._refresh_token(info.customer_id, lazy):
                return None

        try:
            response = await query.fleetcarrier(info.access_token[0])
        except (EpicFail, CapiFail) as error:
            if isinstance(error, EpicFail):
                info.access_token = None
                _LOGGER.warning("Epic authentication failed for '%s'", info.commander)

            else:
                _LOGGER.warning("cAPI request failed for '%s'", info.commander)

            if not lazy:
                await self.push()

            raise error

        if response is None:
            info.carrier = None
            _LOGGER.warning("'%s' is no longer owned by '%s'", callsign, info.commander)

            if not lazy:
                await self.push()

        return response


CAPI_SERVICE = CapiService()
