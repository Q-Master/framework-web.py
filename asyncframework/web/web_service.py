# -*- coding:utf-8 -*-
from typing import Optional, Union, Sequence, Dict, Any, Callable
import asyncio
import socket
from ssl import SSLContext
from aiohttp.web_log import AccessLogger
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import RouteTableDef, UrlDispatcher
from aiohttp.web_runner import BaseSite, AppRunner, TCPSite, UnixSite, SockSite
from asyncframework.app.service import Service
from asyncframework.log.log import get_logger
from .web_application import WebApplication


__all__ = ['WebService']


class WebService(Service):
    """Web application service
    """
    log = get_logger('WebService')

    __host: Optional[Sequence[str]]
    __port: Optional[int]
    __path: Optional[Sequence[str]]
    __sock: Optional[Sequence[socket.socket]]
    __shutdown_timeout: float
    __ssl_context: Optional[SSLContext]
    __reuse_address: Optional[bool]
    __reuse_port: Optional[bool]
    __backlog: int
    __runner: AppRunner
    __access_logger: AbstractAccessLogger
    __access_log_format: str
    __additional_args: Dict[str, Any]
    __app: WebApplication

    @property
    def app(self):
        return self.__app

    def __init__(self, 
        host: Optional[Union[str, Sequence[str]]] = None, port: Optional[int] = None, 
        path: Optional[Union[str, Sequence[str]]] = None, 
        sock: Optional[Union[socket.socket, Sequence[socket.socket]]] = None,
        shutdown_timeout: float = 60.0, 
        ssl_context: Optional[SSLContext] = None, 
        reuse_address: Optional[bool] = None, reuse_port: Optional[bool] = None, backlog: int = 128,
        access_log_class=AccessLogger, access_log_format=AccessLogger.LOG_FORMAT,
        routes: Optional[Union[UrlDispatcher, RouteTableDef]] = None,
        controller_factory: Optional[Callable] = None,
        **additional_app_attrs) -> None:
        """Constructor

        Args:
            host (Optional[Union[str, Sequence[str]]], optional): hostname to bind. Defaults to None.
            port (Optional[int], optional): port to bind. Defaults to None.
            path (Optional[Union[str, Sequence[str]]], optional): unix socket path. Defaults to None.
            sock (Optional[Union[socket.socket, Sequence[socket.socket]]], optional): already opened socket. Defaults to None.
            shutdown_timeout (float, optional): shutdown timeout for server. Defaults to 60.0.
            ssl_context (Optional[SSLContext], optional): SSL context to use with server. Defaults to None.
            reuse_address (Optional[bool], optional): if need to reuse binded address. Defaults to None.
            reuse_port (Optional[bool], optional): if need to reuse binded port. Defaults to None.
            backlog (int, optional): the depth of backlog. Defaults to 128.
            access_log_class (_type_, optional): logger class. Defaults to AccessLogger.
            access_log_format (_type_, optional): logger format. Defaults to AccessLogger.LOG_FORMAT.
            routes (Optional[Union[UrlDispatcher, RouteTableDef]], optional): initialized UrlDispatcher with routes or just route table. Defaults to None.
        """
        super().__init__(linear=False)
        self.__host = [host] if isinstance(host, (str, bytes, bytearray, memoryview)) else host
        self.__port = port
        self.__path = [path] if isinstance(path, (str, bytes, bytearray, memoryview)) else path
        self.__sock = [sock] if isinstance(sock, socket.socket) else sock
        self.__shutdown_timeout = shutdown_timeout
        self.__ssl_context = ssl_context
        self.__reuse_address = reuse_address
        self.__reuse_port = reuse_port
        self.__backlog = backlog
        self.__access_logger = access_log_class
        self.__access_log_format = access_log_format
        self.__controller_factory = controller_factory

        self.__app = WebApplication(
            logger=self.log,
            loop=self.ioloop,
            router=self._make_router(routes),
            controller_factory=self.__controller_factory
        )

        self.__additional_args = additional_app_attrs
        for attr, value in self.__additional_args.items():
            self.__app[attr] = value

    def add_subapp(self, route: str, routes: Union[UrlDispatcher, RouteTableDef]):
        """Add sub application for additional routes

        Args:
            route (str): base path for new routes
            routes (Union[UrlDispatcher, RouteTableDef]): initialized UrlDispatcher with routes or just route table
        """
        subapp = WebApplication(
            logger=get_logger(route),
            loop=self.ioloop,
            router=self._make_router(routes),
            controller_factory=self.__controller_factory 
        )
        for attr, value in self.__additional_args.items():
            subapp[attr] = value
        self.__app.add_subapp(route, subapp)

    async def __start__(self) -> None:
        self.log.debug('Starting to run WebService')
        self.__runner = AppRunner(
            self.__app,
            handle_signals=False,
            access_log_class=self.__access_logger,
            access_log_format=self.__access_log_format,
            access_log=self.log
        )
        await self.__runner.setup()

        self.sites: Sequence[BaseSite] = []
        start_futures = []
        if self.__host is not None:
            for h in self.__host:
                self.log.debug(f'Initializing TCPSite "{h}:{self.__port}"')
                self.sites.append(TCPSite(
                    self.__runner, h, self.__port,
                    shutdown_timeout=self.__shutdown_timeout,
                    ssl_context=self.__ssl_context,
                    backlog=self.__backlog,
                    reuse_address=self.__reuse_address,
                    reuse_port=self.__reuse_port
                ))
                start_futures.append(asyncio.ensure_future(self.sites[-1].start()))
        elif self.__port is not None:
            self.log.debug(f'Initializing TCPSite "0.0.0.0:{self.__port}')
            self.sites.append(
                TCPSite(
                    self.__runner, port=self.__port,
                    shutdown_timeout=self.__shutdown_timeout,
                    ssl_context=self.__ssl_context, 
                    backlog=self.__backlog,
                    reuse_address=self.__reuse_address,
                    reuse_port=self.__reuse_port
                )
            )
            start_futures.append(asyncio.ensure_future(self.sites[-1].start()))

        if self.__path is not None:
            for p in self.__path:
                self.log.debug(f'Initializing UnixSite "{p}"')
                self.sites.append(
                    UnixSite(
                        self.__runner, p,
                        shutdown_timeout=self.__shutdown_timeout,
                        ssl_context=self.__ssl_context,
                        backlog=self.__backlog
                    )
                )
                start_futures.append(asyncio.ensure_future(self.sites[-1].start()))

        if self.__sock is not None:
            for s in self.__sock:
                self.log.debug(f'Initializing SockSite {s}')
                self.sites.append(
                    SockSite(
                        self.__runner, s,
                        shutdown_timeout=self.__shutdown_timeout,
                        ssl_context=self.__ssl_context,
                        backlog=self.__backlog
                    )
                )
                start_futures.append(asyncio.ensure_future(self.sites[-1].start()))

        await asyncio.gather(*start_futures)
        self.log.debug('WebService started succesfully')

    async def __stop__(self, *args):
        self.log.debug('Stopping WebService')
        stop_futures = [asyncio.ensure_future(site.stop()) for site in self.sites]
        await asyncio.gather(*stop_futures)
        await self.__runner._cleanup_server()
        await self.__runner.shutdown()
        self.log.debug('WebService stopped successfully')

    def _make_router(self, routes: Optional[Union[UrlDispatcher, RouteTableDef]]) -> UrlDispatcher:
        if routes is None:
            router = UrlDispatcher()
        elif isinstance(routes, RouteTableDef):
            router = UrlDispatcher()
            router.add_routes(routes)
        else:
            router = routes
        return router