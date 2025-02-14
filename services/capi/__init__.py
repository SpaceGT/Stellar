"""Handles the Frontier Companion API"""

from . import utils
from .service import CAPI_SERVICE
from .worker import CAPI_WORKER

CAPI_SERVICE.sync += utils.sync_carrier
CAPI_WORKER.sync += utils.sync_carrier
