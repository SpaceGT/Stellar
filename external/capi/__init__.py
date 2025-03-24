"""Allows communication with the Companion API."""

from . import auth, query
from .auth import GetEndpoint as AuthEndpoint
from .auth import RefreshFail
from .query import CapiFail
from .query import Endpoint as QueryEndpoint
from .query import EpicFail, TokenFail
