# Anime Telegram Bot

This is a telegram bot for retrieving information about manga and anime

## Usage

1) Create a new Telegram bot using [BotFather](https://t.me/botfather)
1) Set the BOT_TOKEN environment variable as the bot token, do not share this !
1) Create a SECRET_TOKEN environment variable, do not share this !

### Environment Variables

- `PORT` (int): The port the bot server should listen on.
- `HOST` (str): The address the bot server should bind to. Defaults to `0.0.0.0`.
- `DEBUG` (bool): Set to enable debug features.
- `DB_PATH` (str): The path to the sqlite database for storing data.

- `BOT_TOKEN` (str): Your bot token. Can be gotten from [BotFather](https://t.me/botfather). Should be kept secret.
- `SECRET_TOKEN`(str): A string of your choice. Used to verify identity.

- `BOT_WEB_URL` (str): The website your bot is hosted at
- `WEBHOOK_URL` (str): The relative url to your webhook from the `BOT_WEB_URL`.
- `HEALTH_URL` (str): The relative path to your health check url from the `BOT_WEB_URL`.

- `LOG_CHAT_IDS` (list[int]): The list of Telegram chat ids where log data should be sent.
- `DEVELOPER_CHAT_IDS` (list[int]):  The list of Telegram chat ids where exception messages should be sent.

## Deploy to Render

[![Deploy to Render](https://deploy.render.app/button.svg)](https://deploy.render.app/)

1) Set `server.py` as your entry point.

## Run Locally

Prerequisites:

- python >= 3.11

Install: `scripts/install`

- installs dependencies from `requirements.txt`

Run: `scripts/start`

- runs a `uvicorn` server (use for development)

## Helpful Docs

- [python-telegram-bot](https://docs.python-telegram-bot.org/en/stable/index.html)
- [Telegram Bots API](https://core.telegram.org/bots/api)
