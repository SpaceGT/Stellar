"""Caches the shared Google Sheet to keep API rquests low."""

from settings import GOOGLE
from utils import sheets
from utils.sheets import GoogleSheet

SPREADSHEET = GoogleSheet(
    GOOGLE.sheet_id,
    sheets.load_credentials(GOOGLE.credentials, GOOGLE.token),
)
