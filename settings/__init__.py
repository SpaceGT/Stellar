"""Load and provide access to all required confugration files."""

from . import logger
from .loader import CONFIG_DIR, ENV, JSON
from .models import capi, discord, eddn, google, software, timings
from .webhook import Webhook

SOFTWARE = software.factory(JSON["software"])
EDDN = eddn.factory(JSON["eddn"], SOFTWARE)
CAPI = capi.factory(JSON["capi"], SOFTWARE)
DISCORD = discord.factory(JSON["discord"], ENV, CONFIG_DIR)
GOOGLE = google.factory(ENV, CONFIG_DIR)
TIMINGS = timings.factory(JSON["timings"])

logger.root_logger.addHandler(Webhook(SOFTWARE.webhook))
