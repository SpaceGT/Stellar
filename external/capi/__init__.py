"""Allows communication with the Companion API."""

from . import auth, query
from .auth import GetEndpoint as AuthEndpoint
from .query import Endpoint as QueryEndpoint
