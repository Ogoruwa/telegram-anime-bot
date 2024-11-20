from telegram.constants import MessageLimit

from environs import Env
from enum import IntEnum, StrEnum
from logging import INFO, WARNING

env = Env()
env.read_env()


class KeyboardSubject(StrEnum):
    ANIME = "anime"
    MANGA = "manga"
    CHARACTER = "character"


class Language(IntEnum):
    ENGLISH = 1
    ROMAJI = 2
    JAPANESE = 3


class DatabaseTables(StrEnum):
    PREFERENCES = "preferences"
    KEYBOARD_ANIME = "keyboard_anime"
    KEYBOARD_MANGA = "keyboard_manga"
    KEYBOARD_CHARACTER = "keyboard_character"


class Settings:
    PORT: int = env.int("PORT")
    HOST: str = env.str("HOST", "0.0.0.0")
    DB_PATH: str = env.str("DB_PATH")
    DEBUG: bool = env.bool("DEBUG", False)
    LOG_LEVEL: int = INFO if DEBUG else WARNING

    BOT_TOKEN: str = env.str("BOT_TOKEN")
    SECRET_TOKEN: str = env.str("SECRET_TOKEN")
    
    BOT_WEB_URL: str = env.str("BOT_WEB_URL")
    HEALTH_URL: str= env.str("HEALTH_URL", "/health/")
    WEBHOOK_URL: str = env.str("WEBHOOK_URL", "/webhook/")

    LOG_CHAT_IDS: list[int] = [ int(i.strip()) for i in env.list("LOG_CHAT_IDS", []) ]
    DEVELOPER_CHAT_IDS: list[int] = [ int(i.strip()) for i in env.list("DEVELOPER_CHAT_IDS", []) ]

    MIN_MESSAGE_LENGTH: int = MessageLimit.MIN_TEXT_LENGTH
    MAX_MESSAGE_LENGTH: int = MessageLimit.MAX_TEXT_LENGTH
    ALLOWED_TAGS = [ "a", "b", "code", "i", "pre" ]




def get_settings() -> Settings:
    settings = Settings()
    return settings
