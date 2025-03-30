# -*- coding:utf-8 -*-
from typing import Dict, Any, Optional, Generator, TypeVar, Type, Sequence, Tuple
from aiohttp.web import HTTPBadRequest, Request
from aiohttp.helpers import reify
from asyncframework.log.log import get_logger
from packets.packet import Packet
from packets import json


__all__ = ['WebRequest', 'WebRequestArgsPacket']


_not_found = object()
T = TypeVar('T', bound='WebRequestArgsPacket')


class WebRequest(Request):
    """The subclass of `Request` with additional features
    """
    log = get_logger('EnhancedRequest')

    _flat_args: Optional[Dict[str, Any]]
    _flat_headers: Optional[Dict[str, Any]]
    _controller = None

    def __init__(self, *args: Any, controller = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._flat_args = None
        self._flat_headers = None
        self._controller = controller

    @property
    def controller(self) -> Any:
        return self._controller

    @property
    def address(self) -> str:
        """Get the actual hostname from headers

        Returns:
            str: the actual hostname
        """
        return self.headers.get('X-Forwarded-For', self.host)

    @reify
    def remote(self) -> Optional[str]:
        """Get the caller IP from headers

        Returns:
            str: the real IP of the caller
        """
        return self.headers.get('X-Real-IP', super().remote)

    @property
    def flat_headers(self) -> Dict[str, Any]: # type: ignore[override]
        """Flatten the headers

        Returns:
            Dict[str, Any]: the flattened headers
        """
        if self._flat_headers is None:
            self._flat_headers = {}
            aiohttp_headers = super().headers
            for key, value in aiohttp_headers.items():
                v = aiohttp_headers.getall(key)
                self._flat_headers[key] = v if len(v) > 1 else value
        return self._flat_headers

    async def flat_args(self) -> Dict[str, Any]:
        """Flatten the args

        Returns:
            Dict[str, Any]: the flattened args
        """
        if self._flat_args is None:
            decoded_args = {}
            all_args = (await self.post()).copy()
            all_args.extend(self.query)
            for key, value in all_args.items():
                v = all_args.getall(key)
                decoded_args[key] = v if len(v) > 1 else value
            self._flat_args = decoded_args
        return self._flat_args

    async def body(self) -> Optional[str]:
        """Return the body of the request

        Returns:
            Optional[str]: the body of the request if exists
        """
        if self.has_body:
            return await self.text()
        return None

    async def uri(self) -> str:
        """Generate URI from all args.

        Returns:
            str: generated URI
        """
        all_args = await self.flat_args()
        if all_args:
            params = '&'.join(f'{arg}={value}' for arg, value in all_args.items())
            return f'{self.path}?{params}'
        else:
            return self.path

    async def extract_args(self, *arg_names, **defaults) -> Sequence[Any]:
        """Extract all args matching `arg_names` and/or `defaults`
        If defaults exist, the default value for not-found arg will be set.

        Raises:
            HTTPBadRequest: if not all args are found, even with defaults.

        Returns:
            Sequence[Any]: the tuple of extracted values of args
        """
        default_args = dict.fromkeys(arg_names + tuple(defaults.keys()), _not_found)
        default_args.update(defaults)
        self_args = await self.flat_args()
        def next() -> Generator:
            for k,v in default_args.items():
                v = self_args.get(k, v)
                if v is _not_found:
                    raise HTTPBadRequest(reason=f'Missing argument {k}')
                yield v
        return tuple(next())
    
    def get_auth(self) -> Tuple[Optional[str], Optional[str]]:
        auth = self.headers.get('Authorization', None)
        if auth:
            try:
                auth_type, token = auth.split(maxsplit=1)
            except ValueError:
                auth_type, token = None, None
            return(auth_type, token)
        return (None, None)


class WebRequestArgsPacket(Packet):
    """Class to convert request args to Packet
    """
    @classmethod
    async def from_request_for_arg(cls: Type[T], request: WebRequest, arg: str) -> T:
        """Load data for arg explicitly

        Args:
            request (WebRequest): the request
            arg (str): the name of an arg

        Returns:
            T: constructed packet
        """
        data, = await request.extract_args(arg)
        return cls._loads_or_bad_request(data)

    @classmethod
    async def from_request_args(cls: Type[T], request: WebRequest) -> T:
        """Load data from all request args

        Args:
            request (WebRequest): the request

        Returns:
            T: constructed packet
        """
        data = await request.flat_args()
        return cls._load_or_bad_request(data)

    @classmethod
    async def from_request_body(cls: Type[T], request: WebRequest) -> T:
        """Load data from request body

        Args:
            request (WebRequest): the request

        Returns:
            T: constructed packet
        """
        data = await request.body()
        return cls._loads_or_bad_request(data)

    @classmethod
    def _load_or_bad_request(cls: Type[T], data) -> T:
        try:
            return super().load(data)
        except (ValueError, TypeError, AssertionError) as e:
            raise HTTPBadRequest(reason='Error in arguments "{}"'.format(str(e).replace('"', "'")))

    @classmethod
    def _loads_or_bad_request(cls: Type[T], data) -> T:
        try:
            parsed = json.loads(data)
        except (ValueError, TypeError) as e:
            raise HTTPBadRequest(reason=f'Error json deserializing "{e}"')
        else:
            return cls._load_or_bad_request(parsed)
