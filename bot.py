from json import dumps
from traceback import format_exception
from html import escape as html_escape

from telegram.constants import ParseMode
from telegram import BotCommand, Update
from telegram.ext import filters, Application, CommandHandler, MessageHandler, ContextTypes, CallbackContext

from storage import cursor, data_cache, get_user_data
from settings import get_settings, Language, DatabaseTables
from utils import chunkify_html_text, get_logger, remove_update_sensitive_info
from keyboards import AnimeKeyboardHandler, CharacterKeyboardHandler, HelpKeyboardHandler, MangaKeyboardHandler


debug_handlers = set()
settings = get_settings()
logger = get_logger(__name__)



def log_command_usage(func):
    async def log_command(self, update: Update, context: BotContext):
        update_str = dumps(update.to_dict() if isinstance(update, Update) else str(update), indent = 2, ensure_ascii = False)
        update_str = remove_update_sensitive_info(update_str)
        text = f"<pre>update = {html_escape(update_str)}</pre>\n"
        await log_in_channels(text, context)
        return await func(self, update, context)
    return log_command


async def log_in_channels(text: str, context: CallbackContext):
    for chat_id in settings.LOG_CHAT_IDS:
        await context.bot.send_message(chat_id = chat_id, text = text, parse_mode = ParseMode.HTML)
    
 
async def send_to_developers(text: str, context: CallbackContext):
    for chat_id in settings.DEVELOPER_CHAT_IDS:
        chunks = chunkify_html_text(text)
        for chunk in chunks:
            await context.bot.send_message(chat_id = chat_id, text = chunk, parse_mode = ParseMode.HTML)



class BotContext(CallbackContext):
    @classmethod
    def from_update(cls, update: object, application: "Application") -> "BotContext":
        if isinstance(update, Update):
            return cls(application = application)
        return super().from_update(update, application)



class Bot:
    def __init__(self, bot_token: str) -> None:
        """Set up bot application and a web application for handling the incoming requests."""
        
        # Set updater to None so updates are handled by webhook
        context_types = ContextTypes(context = BotContext)
        self.application = Application.builder().token(bot_token).updater(None).context_types(context_types).build()


    async def setup(self, secret_token: str, bot_web_url: str) -> None:
        # Set webhook url and secret_key
        await self.application.bot.set_webhook(url = bot_web_url, secret_token = secret_token)
        await self.set_bot_commands_menu()

        # Add handlers here
        self.application.add_error_handler(self.handle_error)

        self.application.add_handler( CommandHandler("start", self.cmd_start) )
        self.application.add_handler( CommandHandler("help", self.cmd_help) )
        self.application.add_handler( CommandHandler("id", self.cmd_id) )
        self.application.add_handler( CommandHandler("about", self.cmd_about) )

        self.application.add_handler( CommandHandler("anime", self.cmd_anime) )
        self.application.add_handler( CommandHandler("character", self.cmd_character) )
        self.application.add_handler( CommandHandler("manga", self.cmd_manga) )

        if settings.DEBUG:
            self.add_debug_handlers()

            
        self.application.add_handler( AnimeKeyboardHandler().create_handler() )
        self.application.add_handler( CharacterKeyboardHandler().create_handler() )
        self.application.add_handler( MangaKeyboardHandler().create_handler() )
        self.application.add_handler( HelpKeyboardHandler().create_handler() )

        self.application.add_handler( MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member) )
        self.application.add_handler( MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.handle_left_member) )
        self.application.add_handler( MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message) )


    # Bot methods

    async def set_bot_commands_menu(self) -> None:
        # Register commands for bot menu
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Get help about this bot"), 
            BotCommand("about", "Get information about the bot"),

            BotCommand("anime", "Get information about an anime"),
            BotCommand("manga", "Get information about a manga"),
            BotCommand("character", "Get information about a character"),
        ]
        await self.application.bot.set_my_commands(commands)


    # Bot handlers

    async def handle_error(self, update: Update, context: BotContext) -> None:
        """Log the error and send a message to notify the developer."""
        # Log the error first so it can be seen even if something breaks.
        logger.error("Exception while handling an update:", exc_info = context.error)

        # traceback.format_exception returns the usual python message about an exception, but as a
        # list of strings rather than a single string, so we have to join them together.
        tb_list = format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)

        # Build the message with some markup and additional information about what happened.

        update_str = dumps(update.to_dict() if isinstance(update, Update) else str(update), indent = 2, ensure_ascii = False)
        update_str = remove_update_sensitive_info(update_str)
        for text in (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html_escape(update_str)}</pre>\n",

            "<b>Context</b>\n"
            f"<pre><u>context.bot_data</u> = {html_escape(dumps(context.bot_data, indent = 2, ensure_ascii = False))}</pre>\n\n"
            f"<pre><u>context.chat_data</u> = {html_escape(dumps(context.chat_data, indent = 2, ensure_ascii = False))}</pre>\n\n"
            f"<pre><u>context.user_data</u> = {html_escape(dumps(context.user_data, indent = 2, ensure_ascii = False))}</pre>\n\n",
            
            "<b>Traceback</b>\n"
            f"<pre>{html_escape(tb_string)}</pre>\n",
        ):
            for chunk in chunkify_html_text(text):
                await log_in_channels(chunk, context)


    async def handle_message(self, update: Update, context: BotContext) -> None:
        """Handles messages"""
        if not update.effective_message:
            return
        text = "Use /help to get a list of commands"
        await update.effective_message.reply_text(text, reply_to_message_id = update.effective_message.message_id)


    async def handle_new_member(self, update: Update, context: BotContext):
        chat = update.effective_chat
        for member in update.effective_message.new_chat_members:
            if member == context.bot.get_me():
                await log_in_channels( f"Was added to {chat.type} chat: {chat.title} with id: {chat.id}", context )


    async def handle_left_member(self, update: Update, context: BotContext):
        chat = update.effective_chat
        if update.effective_message.left_chat_member == context.bot.get_me():
            await log_in_channels( f"Left {chat.type} chat: {chat.title} with id: {chat.id}", context )



    # Bot commands

    async def cmd_restart(self, update: Update, context: BotContext) -> None:
        if update.effective_user.id is settings.DEVELOPER_CHAT_IDS:
            context.bot_data["restart"] = True


    async def cmd_start(self, update: Update, context: BotContext) -> None:
        user = update.effective_user
        if not user:
            return

        user_data = await get_user_data(user.id, DatabaseTables.PREFERENCES)
        language = user_data['language']

        match language:
            case Language.ENGLISH: 
                text = "Welcome {0} {1}!\nI am {2}\nUse the help command (/help) to view the guide"
            case Language.ROMAJI:
                text = "Hajimemashite {0} {1}!\n Watashi wa {2} desu.\nUse the help command (/help) to view the guide"
            case Language.JAPANESE:
                text = "はじめまして {0} {1}!\nわたしはアリエスです (I am ARIES).\nUse the help command (/help) to open the guide."
            case _:
                raise Exception(f"'{language}' is not a valid language")
        
        text = text.format(user.username, user.name, context.bot.username)
        await update.effective_message.reply_text(text)


    async def cmd_help(self, update: Update, context: BotContext) -> None:
        message = update.effective_message
        text = (
            "I was designed to give you quick and easy access to information about anime and manga.\n"
            "Pick a topic you need help understanding."
        )
        
        keyboard = await HelpKeyboardHandler.generate_markup(update, context)
        await message.reply_text(text, reply_markup = keyboard)


    @log_command_usage
    async def cmd_about(self, update: Update, context: BotContext) -> None:
        message = update.effective_message
        text = (
            "<b>Copyright 2024 Ogoruwa</b>\n\n"
            "This bot is licensed under the <a href='https://opensource.org/license/mit' title='MIT License'>MIT</a>\n\n"
            f"Bot name: {context.bot.username}\nBot handle: {context.bot.name}\n\n"
            "<u>Links</u>\n"
            "Source code: <a href='https://github.com/Ogoruwa/' title='Github repository'>Private, as the bot is still in the alpha stage</a>\n"
            "Documentation: Not yet created\n"
            f"Telegram link: <a href='{context.bot.link}' title='Telegram link'>{context.bot.link}</a>"
        )

        await message.reply_html(text)


    async def cmd_id(self, update: Update, context: BotContext):
        user = update.effective_user
        if user:
            text = f"Your id is {user.id}\nThe chat id is {update.effective_chat.id}"
        else:
            text = "You do not have a user id"
        await update.effective_message.reply_text(text)
    
    
    @log_command_usage
    async def cmd_anime(self, update: Update, context: BotContext) -> None:
        await AnimeKeyboardHandler.handle_first(update, context)
    
    
    @log_command_usage
    async def cmd_character(self, update: Update, context: BotContext) -> None:
        await CharacterKeyboardHandler.handle_first(update, context)
    
    
    @log_command_usage
    async def cmd_manga(self, update: Update, context: BotContext) -> None:
        await MangaKeyboardHandler.handle_first(update, context)


    if settings.DEBUG:
        def debug_handler(func):
            async def wrapper(self, update: Update, context: BotContext):
                if update.effective_user.id not in settings.DEVELOPER_CHAT_IDS:
                    return
                return await func(self, update, context)
            return wrapper 

        @debug_handler
        async def raise_bot_exception(self, update: Update, context: BotContext):
            context.bot.this_method_does_not_exist_not_a_bug_007()

        @debug_handler
        async def print_data_cache(self, update: Update, context: BotContext):
            text = f"<pre>data_cache = {html_escape(dumps(data_cache, indent = 2, ensure_ascii = False))}</pre>"
            await update.effective_message.reply_html(text)

        @debug_handler
        async def execute_sql(self, update: Update, context: BotContext):
            command = cursor.execute(""" """.join(context.args))
            result = command.fetchall()
            text = dumps(result)
            await update.effective_message.reply_text(text)

        def add_debug_handlers(self):
            self.application.add_handler(CommandHandler("raise", self.raise_bot_exception))
            self.application.add_handler(CommandHandler("cache", self.print_data_cache))
            self.application.add_handler(CommandHandler("sql", self.execute_sql))


