
from aiohttp import BasicAuth
from aiohttp.client_exceptions import ConnectionTimeoutError


class ParserSettings:
    """
    Класс для хранения настроек парсера.

    Атрибуты класса используются для конфигурации параметров, таких как:
    - Исключения, при которых следует повторять запросы.
    - HTTP-статусы, при которых следует повторять запросы.
    - Количество попыток повторного запроса.
    - Список прокси для использования в запросах.
    - Таймаут для HTTP-запросов.
    """

    exceptions: list[Exception] = None  # Список исключений, при которых следует повторять запросы (например, ConnectionTimeoutError).
    statuses: set[int] = None # Список HTTP-статусов, при которых следует повторять запросы (например, 500, 502).
    attemps: int = None  # Количество попыток повторного запроса при возникновении ошибок.
    proxies: list[tuple[str, BasicAuth]] = None  # Список прокси для использования в запросах (например, [("http://proxy1", BasicAuth("login", "password")), ...]
    timeout: int = None  # Таймаут для HTTP-запросов (в секундах).
