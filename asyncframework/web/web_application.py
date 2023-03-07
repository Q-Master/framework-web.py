# -*- coding:utf-8 -*-
from typing import Type
import asyncio
from aiohttp.web import Application, Request
from aiohttp.http_parser import RawRequestMessage
from aiohttp.streams import StreamReader
from aiohttp.web_protocol import RequestHandler
from aiohttp.abc import AbstractStreamWriter
from .web_request import WebRequest


__all__ = ['WebApplication']


class WebApplication(Application):
    """Custom WebApplication class for using custom Request
    """
    def _make_request(
        self,
        message: RawRequestMessage,
        payload: StreamReader,
        protocol: RequestHandler,
        writer: AbstractStreamWriter,
        task: "asyncio.Task[None]",
        _cls: Type[Request] = WebRequest,
    ) -> Request:
        return WebRequest(
            message,
            payload,
            protocol,
            writer,
            task,
            self._loop,
            client_max_size=self._client_max_size,
        )
