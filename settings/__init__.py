"""Load and provide access to all required confugration files."""

from . import logger
from .loader import CONFIG_DIR, ENV, JSON
from .models import discord, eddn, google, software
from .webhook import Webhook

SOFTWARE = software.factory(JSON["software"])
EDDN = eddn.factory(JSON["eddn"], SOFTWARE)
DISCORD = discord.factory(JSON["discord"], ENV, CONFIG_DIR)
GOOGLE = google.factory(ENV, CONFIG_DIR)

logger.root_logger.addHandler(Webhook(SOFTWARE.webhook))
