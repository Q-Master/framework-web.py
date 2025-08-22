# -*- coding:utf-8 -*-
from typing import Optional, Union, List
from packets import PacketBase, makeField
from packets.processors import string_t, int_t, bool_t
from asyncframework.app import Script, main, Service
from asyncframework.app.config import Config
from asyncframework.log import get_logger, LoggerTaggingAdapter
from asyncframework.web import WebService, WebRequest, webroute, make_response, WebClient, WebRequestArgsPacket
from aiohttp.web import RouteTableDef, Response


ReplyType = Union[PacketBase, dict, str]

class WebConfig(Config):
    pass

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



class test_request_packet(WebRequestArgsPacket):
    is_healthy: str = makeField(bool_t, name='i', required=True)   # is web service healthy?
    req: str = makeField(string_t, name='r', required=True)   # how much is is healthy?
    reply_id: int = makeField(int_t, name='resp', required=True)   # reply id


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


@routes.post('/packet')
@webroute
async def phealth(request: WebRequest) -> Response:
    controller: Controller = request.controller
    controller.log.tags['ip'] = request.remote
    data = await test_request_packet.from_request_body(request)
    controller.log.info(f'Requesting {data.is_healthy}: {data.req} -> {data.reply_id}')
    return controller.build_response(f'OK {data.reply_id}')


class Web(Service):
    log = get_logger('Web')
    def __init__(self):
        super().__init__(linear=False)
    
    async def __start__(self, *args, **kwargs):
        self.aio_service = WebService(
            host='127.0.0.1',
            port=8080,
            routes=routes,
            controller_factory=controller_factory,
            access_log_format='%a "%r" %s %Tf "%{User-Agent}i"'
        )
        await self.aio_service.start()
        self.log.info('Started example web server')

    async def __stop__(self):
        await self.aio_service.stop()
        self.log.info('Stopped example web server')


class Example(Script):
    log = get_logger('Example')
    def __init__(self, config):
        super().__init__('')

    async def __start__(self, *args, **kwargs):
        self.web_service = Web()
        await self.web_service.start()
        self.log.info('Starting example web script')

    async def __stop__(self, *args):
        self.log.info('Stopping example web script')
        await self.web_service.stop()

    async def __body__(self):
        self.log.info('Body')
        http_client = WebClient()
        result = await http_client.get('http://localhost:8080/health')
        if result.text != 'OK 10':
            self.log.error('NOT HEALTHY')
        else:
            self.log.info(f'GET request healthy')
        result = await http_client.post('http://localhost:8080/packet', json={'i': True, 'r': 'Are you ok?', 'resp': 8})
        if result.text != 'OK 8':
            self.log.error('NOT HEALTHY')
        else:
            self.log.info(f'POST request healthy')
        await http_client.close()


if __name__ == '__main__':
    config =  WebConfig()
    config.init_logging()
    main(Example, config)
