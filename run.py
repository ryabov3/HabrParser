import asyncio

from parser.habr_parser import HabrParser
from parser.settings import ParserSettings


if __name__ == "__main__":
    parser = HabrParser(
        proxies=ParserSettings.proxies,
        exceptions=ParserSettings.exceptions,
        timeout=ParserSettings.timeout,
        attemps=ParserSettings.attemps
    )

    url_blog = "https://habr.com/ru/companies/ru_mts/articles/"
    asyncio.run(parser.parsing_blog(url_blog))