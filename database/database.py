import aiomysql
from pymysql.err import ProgrammingError, DataError
from typing import Optional
from database.config import load_config


# Загрузка конфигурации для подключения к базе данных
config = load_config()


class SqlTable:
    """
    Базовый класс для работы с таблицами в базе данных MySQL.

    Атрибуты:
        host (str): Хост базы данных.
        user (str): Имя пользователя базы данных.
        password (str): Пароль пользователя базы данных.
        db_name (str): Название базы данных.
        connection_pool (Optional[aiomysql.Pool]): Пул соединений с базой данных.
    """

    def __init__(self, host: str, user: str, password: str, db_name: str) -> None:
        """
        Инициализация класса SqlTable.

        :param host: Хост базы данных.
        :param user: Имя пользователя базы данных.
        :param password: Пароль пользователя базы данных.
        :param db_name: Название базы данных.
        """
        self.host = host
        self.user = user
        self.password = password
        self.db_name = db_name
        self.connection_pool: Optional[aiomysql.Pool] = None

    async def connect(self) -> None:
        """
        Устанавливает соединение с базой данных и создает пул соединений.
        """
        self.connection_pool = await aiomysql.create_pool(
            user=self.user,
            host=self.host,
            password=self.password,
            db=self.db_name,
            autocommit=True
        )

    async def close_connect(self) -> None:
        """
        Закрывает пул соединений с базой данных.
        """
        if self.connection_pool:
            self.connection_pool.close()
            await self.connection_pool.wait_closed()

    async def _input_cmd(self, cmd: str) -> Optional[aiomysql.Cursor]:
        """
        Выполняет SQL-запрос в базе данных.

        :param cmd: SQL-запрос для выполнения.
        :return: Курсор базы данных, если запрос выполнен успешно, иначе None.
        """
        try:
            async with self.connection_pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(cmd)
                    return cursor
        except (ProgrammingError, DataError):
            # В случае ошибки выполнения запроса, возвращаем None
            pass


class Comments(SqlTable):
    """
    Класс для работы с таблицей комментариев в базе данных.
    Наследует функциональность от SqlTable.
    """

    async def load_comments(self, *comments: str) -> None:
        """
        Загружает комментарии в таблицу базы данных.

        :param comments: Список комментариев для загрузки.
        """
        for comment in comments:
            # Формируем SQL-запрос для вставки комментария
            cmd = """
            INSERT INTO comments (text_comment)
            VALUES ('{}');
            """.format(comment.replace("'", "''"))
            await self._input_cmd(cmd)


class KeyPhrases(SqlTable):
    """
    Класс для работы с таблицей ключевых фраз в базе данных.
    Наследует функциональность от SqlTable.
    """
    pass


async def initialize_database() -> Comments:
    """
    Инициализирует базу данных и возвращает объект для работы с таблицей комментариев.

    :return: Объект класса Comments для работы с таблицей комментариев.
    """
    comments_table = Comments(
        host=config.host,
        user=config.user,
        password=config.password,
        db_name=config.db_name
    )

    await comments_table.connect()

    return comments_table