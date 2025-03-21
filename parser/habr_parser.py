import asyncio
import aiohttp
from asyncio.exceptions import TimeoutError, CancelledError
from aiohttp_retry import RetryClient, ExponentialRetry

import random

from typing import List, Optional, Tuple, Any

import logging

from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from database.database import initialize_database


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s]%(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)


class HabrParser:
    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        attemps: int = 10,
        statuses: Optional[List[int]] = None,
        exceptions: Optional[List[Exception]] = None,
        timeout: int = 0
    ) -> None:
        """
        Инициализация парсера.

        :param proxies: Список прокси для использования в запросах.
        :param attemps: Количество попыток повторного запроса при ошибках.
        :param statuses: Список HTTP-статусов, при которых повторять запрос.
        :param exceptions: Список исключений, при которых повторять запрос.
        :param timeout: Таймаут для HTTP-запросов.
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.proxies = proxies
        self.retry_options = ExponentialRetry(
            attempts=attemps,
            statuses=statuses,
            exceptions=exceptions
        )
        self.articles_links: List[str] = []  # Список для хранения ссылок на статьи
        self.comments_links: List[str] = []  # Список для хранения ссылок на комментарии
        self.ua = UserAgent()  # Генератор случайных User-Agent

    async def parsing_blog(self, main_url: str) -> None:
        """
        Основной метод для парсинга блога. Получает ссылки на все статьи и парсит их.

        :param main_url: URL главной страницы блога.
        """
        async with aiohttp.ClientSession(timeout=self.timeout, raise_for_status=False) as client_session:
            async with RetryClient(client_session=client_session, retry_options=self.retry_options) as retry_session:
                last_page = await self._get_last_page(retry_session, main_url)

                # Генерация ссылок на все страницы блога
                page_links = [f"{main_url}page{i}/" for i in range(1, last_page + 1)]
                await asyncio.gather(*[
                        asyncio.create_task(self._get_articles_links(retry_session, page_url))
                        for page_url in page_links
                    ])
                await self.parsing_articles(*self.articles_links, parsing_comments=True)
    
    async def parsing_articles(self, *articles_urls: str, parsing_comments=False) -> None:
        """
        Парсинг текста статей и комментариев (опционально) по списку URL статей.

        :param articles_urls: Список URL статей для парсинга.
        """
        db_comment = await initialize_database()
        async with aiohttp.ClientSession(timeout=self.timeout, raise_for_status=False) as client_session:
            async with RetryClient(client_session=client_session, retry_options=self.retry_options) as retry_session:
                await asyncio.gather(*[self._get_text_from_article(retry_session, article_url, db_comment) for article_url in articles_urls])
                if parsing_comments:
                    comments_urls = [f"{article_url}comments/" for article_url in articles_urls]
                    await self.parsing_comments(*comments_urls)
    
    async def parsing_comments(self, *comments_urls: str) -> None:
        """
        Асинхронно парсит комментарии по указанным URL-адресам и сохраняет их в базу данных.

        Args:
            *comments_urls (str): Произвольное количество URL-адресов, по которым будут парситься комментарии.

        Returns:
            None: Функция не возвращает значение, но сохраняет результаты в базу данных.

        Пример использования:
            await parsing_comments("http://example.com/comment1", "http://example.com/comment2")
        """
        db_comment = await initialize_database()
        async with aiohttp.ClientSession(timeout=self.timeout, raise_for_status=False) as client_session:
            async with RetryClient(client_session=client_session, retry_options=self.retry_options) as retry_session:
                await asyncio.gather(*[self._get_text_from_comments(retry_session, comment_url, db_comment) for comment_url in comments_urls])

    async def _get_soup(self, response: aiohttp.ClientResponse) -> BeautifulSoup:
        """
        Преобразует ответ от сервера в объект BeautifulSoup для парсинга HTML.

        :param response: Ответ от сервера.
        :return: Объект BeautifulSoup.
        """
        return BeautifulSoup(await response.text(), "html.parser")

    async def _get_last_page(self, session: RetryClient, url: str) -> int:
        """
        Получает номер последней страницы блога.

        :param session: Сессия для выполнения HTTP-запросов.
        :param url: URL страницы для парсинга.
        :return: Номер последней страницы.
        """
        proxy, proxy_auth = await self._get_proxy()
        headers = {'User-Agent': self.ua.random}
        try:
            async with session.get(url, proxy=proxy, proxy_auth=proxy_auth, headers=headers) as response:
                soup = await self._get_soup(response)
                last_page_number = soup.select_one(
                    "div.tm-pagination__pages > div:nth-child(3) > a:nth-child(1)"
                ).text
                logging.info(f"Номер последней страницы найден: {last_page_number}.")
                return int(last_page_number)
        except (TimeoutError, CancelledError) as exception:
            logging.warning(f"Проблемы с получением последней страницы, ошибка={exception.__class__.__name__}.")

    async def _get_articles_links(self, session: RetryClient, page_url: str) -> None:
        """
        Получает ссылки на статьи с указанной страницы блога.

        :param session: Сессия для выполнения HTTP-запросов.
        :param page_url: URL страницы для парсинга.
        """
        headers = {"User-Agent": self.ua.random}
        proxy, proxy_auth = await self._get_proxy()
        page_number = page_url.split('/')[-2]
        try:
            async with session.get(page_url, proxy=proxy, proxy_auth=proxy_auth, headers=headers) as response:
                soup = await self._get_soup(response)
                articles_links_on_page = [
                    f"https://habr.com{a_tag['href']}"
                    for a_tag in soup.select("a.tm-title__link")
                ]
                logging.info(f"Страница: {page_number}. Ссылки на статьи успешно собраны.")
                self.articles_links.extend(articles_links_on_page)
        except (TimeoutError, CancelledError):
            logging.warning(f"Ошибка подключения, страница: {page_number}.")

    async def _get_text_from_article(self, session: RetryClient, article_page: str, db_comment: Any) -> None:
        """
        Парсит текст статьи и сохраняет его в базу данных.

        :param session: Сессия для выполнения HTTP-запросов.
        :param article_page: URL статьи для парсинга.
        :param db_comment: Объект для работы с базой данных.
        """
        headers = {"User-Agent": self.ua.random}
        proxy, proxy_auth = await self._get_proxy()
        article = article_page.split('/')[-2]
        try:
            async with session.get(article_page, proxy=proxy, proxy_auth=proxy_auth, headers=headers) as response:
                soup = await self._get_soup(response)
                article_text = soup.select_one("div.article-formatted-body").get_text(separator="\n").strip()
                await db_comment.load_comments(article_text)
                logging.info(f"Article={article}. Статья успешно добавлен в базу данных.")
        except (TimeoutError, CancelledError):
            logging.warning(f"Ошибка в обработке текста статьи, article={article}.")

    async def _get_text_from_comments(self, session: RetryClient, comment_url: str, db_comment: Any) -> None:
        """
        Парсит текст комментариев и сохраняет его в базу данных.

        :param session: Сессия для выполнения HTTP-запросов.
        :param comment_url: URL страницы с комментариями.
        :param db_comment: Объект для работы с базой данных.
        """
        headers = {"User-Agent": self.ua.random}
        proxy, proxy_auth = await self._get_proxy()
        article = comment_url.split('/')[-3]
        try:
            async with session.get(comment_url, proxy=proxy, proxy_auth=proxy_auth, headers=headers) as response:
                soup = await self._get_soup(response)
                comments = [comment.text.strip() for comment in soup.select("div.tm-comment__body-content_v2 p")]
                await db_comment.load_comments(*comments)
                logging.info(f"Article={article}. Комментарий добавлен в базу данных.")
        except (TimeoutError, CancelledError):
            logging.warning(f"Ошибка подключения или лимит таймаута комментариев, {article=}.")

    async def _get_proxy(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Возвращает случайный прокси из списка, если он задан.

        :return: Кортеж из прокси и данных для аутентификации (если есть).
        """
        if self.proxies is None:
            return None, None
        return random.choice(self.proxies)