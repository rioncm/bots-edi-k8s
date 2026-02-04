"""
Bots sqlite lib
"""
import re
import sqlite3

reformatparamstyle = re.compile(r"%\((?P<name>[^)]+)\)s")

sqlite3.register_adapter(bool, int)                            # python type -> SQL type
sqlite3.register_converter("BOOLEAN", lambda s: bool(int(s)))  # SQL type -> python type


def connect(database: str) -> sqlite3.Connection:
    """
    :param database:

    :return sqlite3 database connection
    """
    con = sqlite3.connect(
        database,
        factory=BotsConnection,
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=99.0,
        isolation_level='EXCLUSIVE'
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA synchronous=OFF")
    return con


class BotsConnection(sqlite3.Connection):
    """Bots sqlite3.Connection class"""
    # pylint: disable=too-few-public-methods

    def cursor(self) -> sqlite3.Cursor:
        """sqlite3.Connection.cursor"""
        return sqlite3.Connection.cursor(self, factory=BotsCursor)


class BotsCursor(sqlite3.Cursor):
    """
    bots engine uses:
        SELECT * FROM ta WHERE idta=%(idta)s,{'idta':12345})
    SQLite wants:
        SELECT * FROM ta WHERE idta=:idta, {'idta': 12345}
    """
    # pylint: disable=too-few-public-methods

    def execute(self, string, parameters=None):
        """sqlite3.Cursor.execute"""
        if parameters is None:
            sqlite3.Cursor.execute(self, string)
        else:
            query = reformatparamstyle.sub(r":\g<name>", string)
            # botsglobal.logger.debug('sqlite3.Cursor.execute("""%s""")', query)
            sqlite3.Cursor.execute(self, query, parameters)
