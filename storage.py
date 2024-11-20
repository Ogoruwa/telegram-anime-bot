from utils import get_logger
from sqlite3 import connect, Cursor, Connection
from settings import get_settings, Language, DatabaseTables


data_cache = {}
settings = get_settings()
logger = get_logger(__name__)


def setup_storage() -> tuple[Connection, Cursor, dict[str, tuple]]:
    # Setup database
    connection = connect(settings.DB_PATH)
    cursor = connection.cursor()


    cursor.execute(f"""CREATE TABLE IF NOT EXISTS {DatabaseTables.PREFERENCES} (user_id INTEGER PRIMARY KEY, language INTEGER DEFAULT {Language.ENGLISH})""")
    
    # Setup keyboard tables
    for table in DatabaseTables:
        if not table.name.lower().startswith("keyboard_"):
            continue
        cursor.execute(f"""CREATE TABLE iF NOT EXISTS {table} (user_id INTEGER PRIMARY KEY, message_id INTEGER, reply_id INTEGER, step INTEGER DEFAULT 1, current_page INTEGER, last_page INTEGER, kwargs TEXT)""")

    connection.commit()

    # Generate tuple of column names for each table, used for setting their values in the cache
    column_names = { table.value: tuple(i[1] for i in cursor.execute(f"""PRAGMA table_info({table.name})""").fetchall()) for table in DatabaseTables }
    return connection, cursor, column_names

connection, cursor, column_names = setup_storage()


async def setup_data_cache(user_id: int) -> None:
    user_data = {}
    
    # Set the user's cache to the values gotten from the databases for each table
    for table in DatabaseTables:
        tablename = table.value
        
        # Insert an entry for the user in the table
        user_data[tablename] = {}
        sql_string_format = """INSERT OR IGNORE INTO {tablename} (user_id) VALUES (?)"""
        sql_string = sql_string_format.format(tablename = tablename)

        cursor.execute(sql_string, (user_id,))
        connection.commit()
        
        # Iterate over the column name and column value and set them in the cache, ignoring the user_id which is indexed at 0
        for key, value in zip(column_names[tablename][1:], cursor.execute(f"""SELECT * FROM {tablename} WHERE user_id=?""", (user_id,)).fetchone()[1:] ):
            user_data[tablename][key] = value
            
    data_cache[user_id] = user_data
    

async def set_user_data(user_id: int, tablename: str, **changes):
    if user_id not in data_cache:
        await setup_data_cache(user_id)
    
    user_data = data_cache[user_id]
    assert tablename in user_data, f"{tablename} not a valid user data table"

    changes_string =  ", ".join(f"""{key}={changes[key]}""" for key in changes)
    sql_string_format = """UPDATE {tablename} SET {changes_string} WHERE user_id=?"""
    sql_string = sql_string_format.format(tablename = tablename, changes_string = changes_string)
    logger.info(f"\n{sql_string}\n")

    cursor.execute(sql_string, (user_id,))
    connection.commit()

    for key in changes:
        user_data[tablename][key] = changes[key]


# Return cached data in order of definition in database
async def get_user_data(user_id: int, tablename: str) -> dict:
    if user_id not in data_cache:
        await setup_data_cache(user_id)
    
    user_data = data_cache[user_id]
    assert tablename in user_data, f"{tablename} not a valid user data table"
    table = user_data[tablename]
    return table


