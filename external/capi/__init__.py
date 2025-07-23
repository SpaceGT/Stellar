"""Allows communication with the Companion API."""

from . import auth, query
from .auth import CapiFail as CapiAuthFail
from .auth import GetEndpoint as AuthEndpoint
from .auth import NewTokenFail
from .query import CapiFail as CapiQueryFail
from .query import Endpoint as QueryEndpoint
from .query import EpicFail, TokenFail
