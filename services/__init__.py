"""Load all service classes."""

from . import galaxy

from .capi import CAPI_SERVICE, CAPI_WORKER
from .depots import DEPOT_SERVICE
from .rescues import RESCUE_SERVICE
from .restocks import RESTOCK_SERVICE
