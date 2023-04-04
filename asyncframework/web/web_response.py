# -*- coding: utf-8 -*-
from typing import Union, Optional
from aiohttp.web import Response
from packets.packet import PacketBase
from packets._json import json


__all__ = ['make_response']


def make_response(source: Union[PacketBase, dict, str], status: int = 200) -> Response:
    """Create response from server.
    A little sugar to create responses from various types of data
    and automaticaly set the MIME-type.

    Args:
        source (Union[PacketBase, dict, str]): the data to send as a response

    Returns:
        Response: generated response
    """
    rtype: Optional[str] = None
    if isinstance(source, PacketBase):
        res, rtype = source.dumps(), 'application/json'
    elif isinstance(source, dict):
        res, rtype = json.dumps(source), 'application/json'
    else:
        res, rtype = source, None
    return Response(text=res, content_type=rtype, status=status)
