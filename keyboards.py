from enum import StrEnum
from json import loads, dumps
from anilist import AsyncClient

from telegram import error, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler, BaseHandler

from settings import DatabaseTables, Language
from storage import get_user_data, set_user_data
from utils import clamp, remove_unspecified_tags, format_anime, format_character, format_manga



__all__ = (
    "AnimeKeyboardHandler",
    "CharacterKeyboardHandler",
    "HelpKeyboardHandler",
    "MangaKeyboardHandler",
)

class OnePage:
    last = 1
    current = 1
    per_page = 1


class KeyboardHandler:
    """An interface intended for managing Telegram inline keyboards and their callbacks

    Raises:
        NotImplementedError: If methods are not overriden.
    """
    pattern: str = None

    @classmethod
    def create_handler(cls) -> CallbackQueryHandler:
        """Generates a callback query handler.

        Returns:
            Callable: The callback query handler
        """
        handler = CallbackQueryHandler(cls.on_update, pattern = cls.pattern)
        return handler
    
    @classmethod
    async def answer(cls, update: Update, context: CallbackContext) -> bool:
        """Returns a boolean to determine if the callback query should be answered

        Args:
            update (Update): Telegram update object
            context (CallbackContext): Telegram callback context object

        Raises:
            NotImplementedError: Raised if not overriden

        Returns:
            bool: Should query be handled ?
        """
        if not update.effective_user:
            return False
        return True
    
    @classmethod
    async def generate_markup(cls, update: Update, context: CallbackContext) -> InlineKeyboardMarkup:
        """Generate the markup for the keyboard when first created

        Args:
            update (Update): Telegram update object
            context (CallbackContext): Telegram callback context object

        Returns:
            InlineKeyboardMarkup: The keyboard markup
        """
        raise NotImplementedError

    @classmethod
    async def handle(cls, update: Update, context: CallbackContext) -> None:
        """Handle callback queries here

        Args:
            update (Update): Telegram update object
            context (CallbackContext): Telegram callback context object
        """
        raise NotImplementedError
    
    @classmethod
    async def on_update(cls, update: Update, context: CallbackContext):
        if cls.answer(update, context):
            try:
                await update.callback_query.answer()
            except error.BadRequest as exception:
                # The callback query could be too old 
                pass
            return await cls.handle(update, context)



class PaginationKeyboardHandler(KeyboardHandler):
    table_name: str

    @classmethod
    async def get_data(cls, identifier: str, page: int, per_page: int = 1, language: Language = Language.ENGLISH) -> tuple[str, tuple[int, int, int]]:
        raise NotImplementedError


    @classmethod
    async def generate_markup(cls, current_page: int, last_page: int, update: Update, context: CallbackContext) -> InlineKeyboardMarkup:
        user = update.effective_user
        current_page = clamp(current_page, 1, last_page)

        user_data = await get_user_data(user.id, cls.table_name)
        previous_keyboard, step = user_data["message_id"], user_data["step"]

        if previous_keyboard:
            try:    
                await context.bot.delete_message(chat_id = update.effective_chat.id, message_id = previous_keyboard)
            except error.BadRequest:
                # Message might not exist
                pass
            finally:
                await set_user_data(user.id, cls.table_name, message_id = "NULL")

        pattern = cls.pattern.split(":")[0]
        callback_data_previous = f"{pattern}:-{step}"
        callback_data_next = f"{pattern}:{step}"

        keyboard = [
            [ InlineKeyboardButton("Previous", callback_data = callback_data_previous), ] if last_page != 1 else [],
            [ InlineKeyboardButton("Next", callback_data = callback_data_next), ] if current_page != last_page else [],
        ] if last_page != 1 else [] 
        
        markup = InlineKeyboardMarkup(keyboard)
        return markup
    

    @classmethod
    async def handle_first(cls, update: Update, context: CallbackContext) -> None:
        identifier = " ".join(context.args).strip()
        if len(identifier) == 0:
            return
            
        text, pagination = await cls.get_data(identifier, 1)
        text = f"1 of {pagination.last}\n\n" + text
        kwargs = f'\'{dumps({"identifier": identifier})}\''
        text = remove_unspecified_tags(text)
        
        keyboard = await cls.generate_markup(pagination.current, pagination.last, update, context)
        message = await update.effective_message.reply_html(text, reply_to_message_id = update.effective_message.message_id, reply_markup = keyboard)
        await set_user_data(update.effective_user.id, cls.table_name, message_id = message.id, reply_id = update.effective_message.message_id, current_page = pagination.current, last_page = pagination.last, kwargs = kwargs)


    @classmethod
    async def handle_next(cls, update: Update, context: CallbackContext) -> None:
        query = update.callback_query
        data = query.data.split(":")
        step = int(data[1])
        
        pagination = await get_user_data(update.effective_user.id, cls.table_name)
        # Current page is None, this happens when the bot server was restarted and the database is empty
        if not pagination["current_page"]:
            await update.effective_message.reply_text("Please run the command again", reply_to_message_id = update.effective_message.id)
            return

        next_page = clamp(pagination["current_page"] + step, 1, pagination["last_page"])
        if next_page == pagination["current_page"]:
            return
        
        kwargs = pagination["kwargs"]
        kwargs = loads(kwargs.strip("'"))
        kwargs["page"] = next_page

        text, _ = await cls.get_data(**kwargs)
        text = remove_unspecified_tags(text)
        text = f"{next_page} of {pagination['last_page']}\n\n" + text

        keyboard = await cls.generate_markup(next_page, pagination["last_page"], update, context)
        try:
            message = await update.effective_message.reply_html(text, reply_to_message_id = pagination["reply_id"], reply_markup = keyboard)
        
        except error.BadRequest:
            # Maybe message with reply id has been deleted
            message = await update.effective_message.reply_html(text, reply_markup = keyboard)

        await set_user_data(update.effective_user.id, cls.table_name, message_id = message.id, current_page = next_page)


    @classmethod
    async def handle(cls, update: Update, context: CallbackContext) -> None:        
        if update.callback_query:
            await cls.handle_next(update, context)
        
        else:
            await cls.handle_first(update, context)
        


class AnimeKeyboardHandler(PaginationKeyboardHandler):
    client = AsyncClient()
    pattern = "anime:(-)?[0-9]+"
    table_name = DatabaseTables.KEYBOARD_ANIME


    @classmethod
    async def get_data(cls, identifier: str, page: int, per_page: int = 1, language: Language = Language.ENGLISH) -> tuple[str, tuple[int, int, int]]:
        """Retrieves anime with specified identifier

        Args:
            identifier (str): The anime identifier, use a numeric string to get a single anime or otherwise to get animes with matching titles
            page (int): The page to return
            per_page (int): The number of anime per paage. Defaults to 1
            language (Language, optional): Language the text should be returned in. This currently only affects the title. Defaults to Language.ENGLISH.

        Returns:
            tuple[str, tuple[int, int, int]]: Tuple containing the anime text and tuple containing three numbers which represent the pagination: total number of matched anime, current page, max page
        """        
        text = ""
        if identifier.isnumeric():
            animes = await cls.client.get_anime(identifier)
            animes = [animes] if animes else animes # Make it a list if not None
            pagination = OnePage()
        
        else:
            animes, pagination = await cls.client.search_anime(identifier, per_page, page)
            animes_new = []
            for anime in animes:
                i = await cls.client.get_anime(anime.id)
                animes_new.append(i)
            
            animes = animes_new
        
        
        if animes:
            for anime in animes:
                text += format_anime(anime, language)
        
        else:
            text = f"Anime '{identifier}' not found"

        text = remove_unspecified_tags(text)
        return text, pagination



class CharacterKeyboardHandler(PaginationKeyboardHandler):
    client = AsyncClient()
    pattern = "character:(-)?[0-9]+"
    table_name = DatabaseTables.KEYBOARD_CHARACTER
    

    @classmethod
    async def get_data(cls, identifier: str, page: int, per_page: int = 1, language: Language = Language.ENGLISH) -> tuple[str, tuple[int, int, int]]:
        text = ""
        if identifier.isnumeric():
            characters = await cls.client.get_character(identifier)
            characters = [characters] if characters else characters # Make it a list if not None
            pagination = OnePage()
        
        else:
            characters, pagination = await cls.client.search_character(identifier, per_page, page)
            characters_new = []
            for character in characters:
                i = await cls.client.get_character(character.id)
                characters_new.append(i)
            
            characters = characters_new
        
        
        if characters:
            for character in characters:
                text += format_character(character, language)
        
        else:
            text = f"Character '{identifier}' not found"

        text = remove_unspecified_tags(text)
        return text, pagination



class MangaKeyboardHandler(PaginationKeyboardHandler):
    client = AsyncClient()
    pattern = "manga:(-)?[0-9]+"
    table_name = DatabaseTables.KEYBOARD_MANGA

    @classmethod
    async def get_data(cls, identifier: str, page: int, per_page: int = 1, language: Language = Language.ENGLISH) -> tuple[str, tuple[int, int, int]]:
        text = ""
        if identifier.isnumeric():
            mangas = await cls.client.get_manga(identifier)
            mangas = [mangas] if mangas else mangas # Make it a list if not None
            pagination = OnePage()
        
        else:
            mangas, pagination = await cls.client.search_manga(identifier, per_page, page)
            mangas_new = []
            for manga in mangas:
                i = await cls.client.get_manga(manga.id)
                mangas_new.append(i)
            
            mangas = mangas_new
        
        
        if mangas:
            for manga in mangas:
                text += format_manga(manga, language)
        
        else:
            text = f"Manga '{identifier}' not found"
        
        text = remove_unspecified_tags(text)
        return text, pagination



class HelpKeyboardHandler(KeyboardHandler):
    class HelpTopic(StrEnum):
        ANIME = "help:anime"
        CHARACTER = "help:character"
        MANGA = "help:manga"
        ABOUT = "help:about"
    
    pattern = "help:(.)*"
    

    @classmethod
    async def generate_markup(cls, update: Update, context: CallbackContext) -> InlineKeyboardMarkup:
        TOPIC = cls.HelpTopic

        keyboard = [
            [
                InlineKeyboardButton("Anime", callback_data=TOPIC.ANIME),
                InlineKeyboardButton("Characters", callback_data=TOPIC.CHARACTER),
                InlineKeyboardButton("Manga", callback_data=TOPIC.MANGA),
            ],
            [
                InlineKeyboardButton("About", callback_data=TOPIC.ABOUT),
            ],
        ]

        markup = InlineKeyboardMarkup(keyboard)
        return markup
    
    
    @classmethod
    async def handle(cls, update: Update, context: CallbackContext) -> None:
        TOPIC = cls.HelpTopic
        query = update.callback_query
        topic = query.data
    

        match topic:
           case TOPIC.ANIME:
                text = (
                    """Use the /anime command to request anime data\n"""
                    """\n/anime <anime title>\n"""
                    """\nFor exmaple: /anime Awesome Anime"""
                    )
           case TOPIC.CHARACTER:
                text = (
                    """Use the /character command to request character data\n"""
                    """\n/character <character name>\n"""
                    """\nFor example: /character Cool Character"""
                )
           case TOPIC.MANGA:
                text = (
                    """Use the /manga command to request character data\n"""
                    """\n/manga <manga title>\n"""
                    """For example: /manga Mid Manga\n"""
                )
           case TOPIC.ABOUT:
                text = (
                    """Get information about this bot\n"""
                    """\n/about\n"""
                )
           case _:
                text = (
                    """I was designed to give you quick and easy access to anime and manga related information.\n"""
                    """Pick a topic you need help understanding."""
                )
        
        if text == query.message.text:
            return
        
        markup = await cls.generate_markup(update, context)
        await query.edit_message_text(text, reply_markup = markup)
