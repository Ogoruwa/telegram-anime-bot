import re
from bs4 import BeautifulSoup
from logging import getLogger, basicConfig

from settings import get_settings, Language 



settings = get_settings()
basicConfig( format = "%(asctime)s - %(name)s -%(levelname)s - %(message)s", level = settings.LOG_LEVEL )


def get_logger(name: str):
    logger = getLogger(name)
    return logger
logger = get_logger(__name__)


def remove_update_sensitive_info(update: str) -> str:
    pattern = '(' + ')|('.join(["\"id\": .*,", "\"last_name\": \".*\",", "\"first_name\": \".*\",", "\"username\": \".*\","]) + ')'
    result = re.sub(pattern, "", update)
    return result


def clamp(value: int, least: int, most: int):
    return max( least, min(value, most) )


def complete_html_tags(html_string: str) -> str:
    """Completes the html tags in a string, closes tags and adds opening tags

    Args:
        html_string (str): The html string to complete 

    Returns:
        str: The edited string
    """
    stack = []
    index = 0
    result = []
    completed_html = []

    # Find all tags in the HTML string
    while index < len(html_string):
        if html_string[index] == '<':
            tag_start = index
            index += 1
            while index < len(html_string) and html_string[index] != '>':
                index += 1
            if index < len(html_string):
                tag_end = index + 1
                tag = html_string[tag_start:tag_end]
                result.append(tag)
        index += 1

    # Process each tag
    for tag in result:
        if tag.startswith('</'):
            # Closing tag
            if stack and stack[-1] == tag[2:-1]:
                stack.pop()
                completed_html.append(tag)
            else:
                # Handle unmatched closing tag (optional)
                pass
        else:
            # Opening tag
            stack.append(tag[1:-1])
            completed_html.append(tag)

    # Add any missing closing tags
    for missing_tag in reversed(stack):
        completed_html.append(f'</{missing_tag}>')

    return ''.join(completed_html)



def chunkify_text(text: str, chunk_length: int = settings.MAX_MESSAGE_LENGTH) -> list[str]:
    """Splits a string into chunks based on maximum length specified
    
    Args:
        text (str): The string to split into chunks
        chunk_length (int, optional): The length of each chunk. Defaults to settings.MAX_MESSAGE_LENGTH.

    Returns:
        list[str]: The string, split into chunks
    """
    chunks = []
    for start in range(0, len(text), chunk_length):
        end = start + chunk_length
        chunk = text[start:end] if end < len(text) else text[start:]
        chunks.append(chunk)
    return chunks


def chunkify_html_text(text: str, chunk_length: int = settings.MAX_MESSAGE_LENGTH) -> list[str]:
    """Splits a html string into chunks based on maximum length specified
    
    Args:
        text (str): The html string to split into chunks
        chunk_length (int, optional): The length of each chunk. Defaults to settings.MAX_MESSAGE_LENGTH.

    Returns:
        list[str]: The string, split into chunks
    """

    chunks = []
    length = len(text)
    buffer_length = int(chunk_length * 0.8)

    for start in range(0, length, buffer_length):
        end = start + buffer_length
        chunk = text[start:end] if end < length else text[start:]
        chunk = "<pre></pre>" if len(chunk.strip()) == 0 else chunk
        soup = BeautifulSoup(chunk, features = "html.parser")
        chunk = remove_unspecified_tags(soup.decode())
        chunks.append(chunk)

    return chunks
 

def remove_unspecified_tags_regex(text: str, tags: list[str] = settings.ALLOWED_TAGS) -> str:
    """Removes html tags that are not in the given list, completely.
    About 8x faster than using BeautifulSoup

    Args:
        text (str): The string to perfrom the operation on
        tags (list[str], optional): The tags that should remain in the string. Defaults to settings.ALLOWED_TAGS.

    Returns:
        str: The string with unlisted tags removed
    """
    if tags is None:
        return text
    else:
        result = re.sub(r"</?(?!(?:" + "|".join(tags) + r")\b)[a-z](?:[^>\"']|\"[^\"]*\"|'[^']*')*>", '', text)
        return result


def remove_unspecified_tags(text: str, tags: list[str] = settings.ALLOWED_TAGS) -> str:
    """Removes html tags that are not in the given list, completely, using BeautifulSoup
    Slower than using regex but more robust.

    Args:
        text (str): The string to perfrom the operation on
        tags (list[str], optional): The tags that should remain in the string. Defaults to settings.ALLOWED_TAGS.

    Returns:
        str: The string with unlisted tags removed
    """
    if not tags or len(text.strip()) == 0:
        return text
    else:
        def recurse(element: BeautifulSoup):            
            if element.name is None:
                return
            
            for child in element.children:
                recurse(child)
            if element.name not in tags:
                element.unwrap()
        
        text = text.replace("<br/>", "\n")
        soup = BeautifulSoup(text, features = "html.parser")
        for child in soup.children:
            recurse(child)
        result = soup.decode()
        return result


def format_anime(anime, language: Language = Language.ENGLISH) -> str:
    titles = "\n".join(get_media_titles(anime, language)).replace("\n\n", "\n")
    characters = "\n\n".join([ "\n ".join(get_character_names(character, language)) for character in get_main_characters(anime) ])
    text = (
            f"ID: {anime.id}\n\n"
            f"<b>Titles</b>\n"
            f"{titles}\n\n"
            "<b>Description</b>\n"
            f"<pre>  <i>{getattr(anime, 'description_short', getattr(anime, 'description', 'No description'))}</i></pre>\n\n"
            
            "<b>Details</b>\n"
            f"Country: {getattr(anime, 'country', 'Not known')}\n"
            f"Episodes: {getattr(anime, 'episodes', 'Not known')}\n"
            f"Format: {getattr(anime, 'format', 'Not known')}\n"
            f"Source: {getattr(anime, 'source', '').title()}\n"
            
            f"Status: {getattr(anime, 'status', 'Status not available').title()}\n"
            f"Season: {getattr(getattr(anime, 'season', 'Not known'), 'name', 'Not known')}\n"
            f"Started: {getattr(getattr(anime, 'start_date', ''), 'year', 'Not known')}\n"
            f"Ended: {getattr(getattr(anime, 'end_date', ''), 'year', 'Not known')}\n\n"

            "<b>Extra Info</b>\n"
            f"<i>Genres</i>: {', '.join(getattr(anime, 'genres', []))}\n\n"
            f"<i>Tags</i>: {', '.join(getattr(anime, 'tags', []))}\n\n"
            f"<i>Studios</i>: {', '.join(getattr(anime, 'studios', []))}\n\n"
            
            f"<b>Main characters</b>\n {characters}\n\n"
            f"Url: <a href='{getattr(anime, 'url', '')}' title='Anilist url'>{getattr(anime, 'url', '')}</a>\n"
        )
    
    return text


def format_character(character, language: Language = Language.ENGLISH) -> str:
    names = "\n".join(get_character_names(character)).replace("\n\n", "\n")
    description = getattr(character, 'description_short', getattr(character, 'description', 'No description').replace('!~','\n  ').replace('~!','\n  ').replace('__', ''))
    text = (
        f"ID: {character.id}\n\n"
        "<b>Names</b>\n"
        f"{names}\n\n"
        
        "<b>Description</b>\n"
        f"<pre>  <i>{description}</i></pre>\n\n"
        
        "<b>Details</b>\n"
        f"Gender: {getattr(character, 'gender', 'Not known')}\n"
        f"Age: {getattr(character, 'age', 'Not known')}\n"
        f"DOB: {getattr(getattr(character, 'birth_date', ''), 'year', 'Not known')}\n"
        f"Role: {getattr(character, 'role', 'Not known')}\n\n"

        "<b>Appearances</b>\n"
        f"{get_character_media(character, language)}"
        
        f"Url: <a href='{getattr(character, 'url', '')}' title='Anilist url'>{getattr(character, 'url', '')}</a>"
    )
    return text


def format_manga(manga, language: Language = Language.ENGLISH) -> str:
    titles = "\n".join(get_media_titles(manga, language)).replace("\n\n", "\n")
    characters = "\n\n".join([ "\n ".join(get_character_names(character, language)) for character in get_main_characters(manga) ])
    text = (
        f"ID: {manga.id}\n\n"
        f"<b>Titles</b>\n"
        f"{titles}\n\n"
        "<b>Description</b>\n"
        f"<pre>  <i>{getattr(manga, 'description_short', getattr(manga, 'description', 'No description'))}</i></pre>\n\n"
        
        "<b>Details</b>\n"
        f"Country: {getattr(manga, 'country', 'Not known')}\n"
        f"Episodes: {getattr(manga, 'episodes', 'Not known')}\n"
        f"Format: {getattr(manga, 'format', 'Not known')}\n"
        f"Source: {getattr(manga, 'source', '').title()}\n"
        
        f"Status: {getattr(manga, 'status', 'Status not available').title()}\n"
        f"Season: {getattr(getattr(manga, 'season', 'Not known'), 'name', 'Not known')}\n"
        f"Started: {getattr(getattr(manga, 'start_date', ''), 'year', 'Not known')}\n"
        f"Ended: {getattr(getattr(manga, 'end_date', ''), 'year', 'Not known')}\n\n"

        "<b>Extra Info</b>\n"
        f"<i>Genres</i>: {', '.join(getattr(manga, 'genres', []))}\n\n"
        f"<i>Tags</i>: {', '.join(getattr(manga, 'tags', []))}\n\n"
        
        f"<b>Main characters</b>\n {characters}\n\n"
        f"Url: <a href='{getattr(manga, 'url', '')}' title='Anilist url'>{getattr(manga, 'url', '')}</a>"
        )
    return text


def get_media_titles(media: dict, language: Language = Language.ENGLISH) -> list[str]:
    romaji = getattr(getattr(media, "title", ""), "romaji", "No romaji title" )
    native = getattr(getattr(media, "title", ""), "native", "No japanese title" )
    english = getattr(getattr(media, "title", ""), "english", "No english title")

    match language:
        case Language.ROMAJI:
            titles = { romaji, english, native }
        case Language.JAPANESE:
            titles = { native, english, romaji }
        case Language.ENGLISH:
            titles = { english, romaji, native }
        case _:
            raise Exception ("'{language}' is not a valid language")
    return list(titles)


def get_character_names(character: dict, language: Language = Language.ENGLISH) -> list[str]:
    native = getattr(getattr(character, "name", ""), "native", "No japanese name" )
    alternative = getattr(getattr(character, "name", ""), "full", "No english name" )

    match language:
        case Language.JAPANESE:
            names = { native, alternative }
        case Language.ENGLISH | Language.ROMAJI:
            names = { alternative, native }
        case _:
            raise Exception ("'{language}' is not a valid language")
    return list(names)


def get_character_media(character: dict, language: Language = Language.ENGLISH) -> str:
    text = ""
    
    for media, _ in zip(getattr(character, 'media', []), range(8)):
        titles = "\n".join(get_media_titles(media))
        text += titles + "\n\n"

    return text


def get_main_characters(anime: dict) -> list[dict]:
    characters = []
    for character in getattr(anime, 'characters', []):
        if getattr(character, 'role', '').upper() == "MAIN":
            characters.append(character)
    return characters

