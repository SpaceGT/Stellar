# Stellar
An application designed to manage the [STAR Initiative](https://fcoc.space/) in Elite Dangerous.

## Setup
All referenced files should be in `config/`.
1. Create a a Google Application utilising the [SheetsAPI](https://developers.google.com/sheets/api/reference/rest).
2. Generate and save OAuth credentials as `credentials.json`.
3. Create `config.json` and populate according to the [schema](/settings/schema.json).
4. In `.env` add your `DISCORD_TOKEN` and `GOOGLE_SHEET_ID`.
5. Copy your memes and resources to `media/`.
6. [Download](https://www.edsm.net/img/galaxyBackgroundV2.jpg) `galaxy.jpg`.

## Features
Here are just some of the things Stellar does:
- Creates tasks to resupply depots.
- Handles rescue tasks for stranded players.
- Sends market data back to EDDN.
- Provides infromation on previous tasks.
- Summarisies Colonia Bridge tritium levels.
- Finds the closest depots to a system.
