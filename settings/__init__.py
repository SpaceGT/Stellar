"""Load and provide access to all required confugration files."""

from . import logger, webhook
from .loader import CONFIG_DIR, ENV, JSON
from .models import capi, discord, eddn, google, software, timings, webhooks

logger.setup()
webhook.setup(webhooks.factory(JSON["webhooks"]))

SOFTWARE = software.factory(JSON["software"])
EDDN = eddn.factory(JSON["eddn"], SOFTWARE)
CAPI = capi.factory(JSON["capi"], SOFTWARE)
DISCORD = discord.factory(JSON["discord"], ENV, CONFIG_DIR)
GOOGLE = google.factory(ENV, CONFIG_DIR)
TIMINGS = timings.factory(JSON["timings"])
