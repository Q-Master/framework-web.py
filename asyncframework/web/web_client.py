# -*- coding:utf-8 -*-
from typing import Optional, Dict, Any
import aiohttp
import asyncio
import time
from asyncframework.log.log import get_logger
from packets import json


__all__ = ['WebClient', 'WebClientResponse']


class WebClientResponse():
    """Web client response for easy use
    """
    __slots__ = ['__status', '__method', '__text', '__json', '__headers']

    __status: int
    __method: str
    __text: str
    __json: Any
    __headers: Dict[str, str]

    def __init__(self, status: int, method: str, text: str, json: Any, headers: Dict[str, str]) -> None:
        self.__status = status
        self.__method = method
        self.__text = text
        self.__json = json
        self.__headers = headers

    @property
    def status(self) -> int:
        return self.__status
    
    @property
    def method(self) -> str:
        return self.__method

    @property
    def text(self) -> str:
        return self.__text

    @property
    def json(self) -> Any:
        return self.__json

    @property
    def headers(self) -> Dict[str, str]:
        return self.__headers


class WebClient:
    """Simple web client class with session
    """
    log = get_logger('WebClient')
    _client_timeout: float
    _client: Optional[aiohttp.ClientSession]
    _session_timeout: float
    _close_after_task: Optional[asyncio.Future]
    _wait_open: Optional[asyncio.Future]
    _last_req_time: float
    _force_close: bool
    _limit: int

    def __init__(self, request_timeout: float = 10, session_timeout: float = 600.0, force_close: bool =False, limit: int = 100):
        """Constructor

        Args:
            request_timeout (float, optional): request timeout in seconds. Defaults to 10.
            session_timeout (float, optional): session timeout in seconds. Defaults to 600.
            force_close (bool, optional): if True will force close and do reconnect after each request (and between redirects). Defaults to False.
            limit (int, optional): max amount of simultaneous connections. Defaults to 100.
        """
        self._client_timeout = request_timeout
        self._client = None
        self._session_timeout = session_timeout
        self._close_after_task = None
        self._wait_open = None
        self._last_req_time = 0
        self._force_close = force_close
        self._limit = limit

    async def get(self, url: str, **kwargs) -> WebClientResponse:
        """GET request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('GET', url, **kwargs)

    async def head(self, url: str, **kwargs) -> WebClientResponse:
        """HEAD request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('HEAD', url, **kwargs)

    async def options(self, url: str, **kwargs) -> WebClientResponse:
        """OPTIONS request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('OPTIONS', url, **kwargs)

    async def trace(self, url: str, **kwargs) -> WebClientResponse:
        """TRACE request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('TRACE', url, **kwargs)

    async def patch(self, url: str, **kwargs) -> WebClientResponse:
        """PATCH request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('PATCH', url, **kwargs)

    async def post(self, url: str, **kwargs) -> WebClientResponse:
        """POST request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('POST', url, **kwargs)

    async def put(self, url: str, **kwargs) -> WebClientResponse:
        """PUT request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('PUT', url, **kwargs)

    async def delete(self, url: str, **kwargs) -> WebClientResponse:
        """DELETE request

        Args:
            url (str): URL

        Returns:
            WebClientResponse: the response
        """
        return await self._request('DELETE', url, **kwargs)

    async def close(self, wait: bool = False):
        """Close session and all the active connections.
        The opened session callback will be cancelled if wait is False.

        Args:
            wait (bool, optional): if to wait for session to close. Defaults to False.
        """
        old_client, self._client, old_close, self._close_after_task = self._client, None, self._close_after_task, None
        if old_client and not old_client.closed:
            await old_client.close()
        if old_close and not old_close.done():
            if not wait:
                old_close.cancel()

    async def _close_after(self):
        try:
            while True:
                self.log.debug(f'Sleeping for {self._session_timeout} sec')
                await asyncio.sleep(self._session_timeout)
                if time.time() >= self._last_req_time + self._session_timeout:
                    self.log.warn('Close session by timeout')
                    await self.close(wait=True)
                    break
                else:
                    self.log.debug(f'Resetting timeout {time.time()} {self._last_req_time + self._session_timeout}')
        except asyncio.CancelledError:
            pass

    async def _request(self, method: str, url: str, **kwargs) -> WebClientResponse:
        if not self._client:
            await self._init_session()

        self._last_req_time = time.time()

        if self._client is None:
            self.log.error(f'ClientSession is None!')
            raise RuntimeError(f'Somehow ClientSession is None!')
        
        async with self._client.request(method, url, **kwargs) as resp:
            try:
                js = await resp.json(loads=json.loads)
            except aiohttp.client_exceptions.ContentTypeError:
                js = None
            r = WebClientResponse(
                status = resp.status,
                method = resp.method,
                text = await resp.text(),
                json = js,
                headers = dict(resp.headers)
            )
            return r

    async def _init_session(self):
        if self._wait_open and not self._wait_open.done():
            await self._wait_open
            self._wait_open = None
        else:
            self._wait_open = asyncio.Future()
            self.log.debug(f'Opening session with timeout: {self._client_timeout}')
            client_timeout = aiohttp.ClientTimeout(total=self._client_timeout)
            tcp = aiohttp.TCPConnector(force_close=self._force_close, limit=self._limit)
            self._client = aiohttp.ClientSession(connector=tcp, timeout=client_timeout, json_serialize=json.dumps)
            self._close_after_task = asyncio.ensure_future(self._close_after())
            self._wait_open.set_result(None)

