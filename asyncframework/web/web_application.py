# -*- coding:utf-8 -*-
from typing import Type, Optional, Callable, Mapping, Any, Iterable
import asyncio
from logging import Logger
from aiohttp.web import Application, Request
from aiohttp.web_urldispatcher import UrlDispatcher
from aiohttp.log import web_logger
from aiohttp.http_parser import RawRequestMessage
from aiohttp.streams import StreamReader
from aiohttp.web_protocol import RequestHandler
from aiohttp.abc import AbstractStreamWriter
from .web_request import WebRequest


__all__ = ['WebApplication']


class WebApplication(Application):
    """Custom WebApplication class for using custom Request
    """

    def __init__(self, *, 
        controller_factory: Optional[Callable] = None,
        logger: Logger = web_logger, 
        router: Optional[UrlDispatcher] = None, 
        middlewares: Iterable[Callable] = (), 
        handler_args: Optional[Mapping[str, Any]] = None, 
        client_max_size: int = 1024 ** 2, 
        loop: Optional[asyncio.AbstractEventLoop] = None, 
        ) -> None:
        super().__init__(logger=logger, router=router, middlewares=middlewares, handler_args=handler_args, client_max_size=client_max_size, loop=loop)
        self._controller_factory = controller_factory
    
    def _make_request(
        self,
        message: RawRequestMessage,
        payload: StreamReader,
        protocol: RequestHandler,
        writer: AbstractStreamWriter,
        task: "asyncio.Task[None]",
        _cls: Type[Request] = Request,
    ) -> Request:
        req = WebRequest(
            message,
            payload,
            protocol,
            writer,
            task,
            self._loop,
            client_max_size=self._client_max_size,
            controller=self._controller_factory() if self._controller_factory else None
        )
        return req

    def set_loop(self, ioloop: asyncio.AbstractEventLoop):
        self._set_loop(ioloop)
        for app in self._subapps:
            app._set_loop(ioloop)
