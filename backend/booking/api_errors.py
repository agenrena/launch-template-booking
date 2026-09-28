from core.api_errors import exception_handler as core_handler
from rest_framework.response import Response

from .services import BookingError


def exception_handler(exc, context):
    if isinstance(exc, BookingError):
        return Response(exc.body, status=409)
    return core_handler(exc, context)
