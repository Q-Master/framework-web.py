# -*- coding:utf-8 -*-
import unittest
from typing import Optional, Union, List
from packets import PacketBase
from asyncframework.log import get_logger, LoggerTaggingAdapter
from asyncframework.web import WebService, WebRequest, webroute, make_response, WebClient
from aiohttp.web import RouteTableDef, Response


ReplyType = Union[PacketBase, dict, str]


class Controller():
    _log = get_logger('Controller')
    def __init__(self, init_code: int) -> None:
        self.init_code = init_code
        self.log = LoggerTaggingAdapter(self.__class__._log)

    def build_response(self, source: Union[List[ReplyType], ReplyType], status: int = 200) -> Response:
        if isinstance(source, list):
            res = [x.dump() if isinstance(x, PacketBase) else x for x in source]
        else:
            res = source
        return make_response(res, status=status)


def controller_factory() -> Optional['Controller']:
    return Controller(10)

routes = RouteTableDef()

@routes.get('/health')
@webroute
async def health(request: WebRequest) -> Response:
    controller: Controller = request.controller
    ip = request.remote
    controller.log.tags['ip'] = ip
    controller.log.info('health ok')
    return controller.build_response(f'OK {controller.init_code}')


class WebTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_webservice(self):
        aio_service = WebService(
            host='localhost',
            port=8080,
            routes=routes,
            controller_factory=controller_factory,
            access_log_format='%a "%r" %s %Tf "%{User-Agent}i"'
        )
        await aio_service.start()

        http_client = WebClient()
        result = await http_client.get('http://localhost:8080/health')
        self.assertEqual(result.text, 'OK 10')
        await http_client.close()
        await aio_service.stop()
