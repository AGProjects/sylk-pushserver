from typing import Union

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from pushserver.resources import settings
from pushserver.resources.utils import pick_log_function


async def validation_exception_handler(request: Request,
                                       exc: Union[RequestValidationError,
                                                  ValidationError]) -> JSONResponse:
    host, port = request.scope['client'][0], request.scope['client'][1]
    account = None
    error_msg = None
    code = 400
    status_code = status.HTTP_400_BAD_REQUEST

    for entry in exc.errors():
        if 'found' in entry['msg'] or 'configured' in entry['msg']:
            status_code = status.HTTP_404_NOT_FOUND
            code = 404

    if not error_msg:
        if '__root__' not in exc.errors()[0]["loc"][2]:
            error_msg = f'{exc.errors()[0]["msg"]}: {exc.errors()[0]["loc"][2]}'
        else:
            error_msg = exc.errors()[0]["msg"]

    try:
        request_id = f"{exc.body['event']} - " \
                     f"{exc.body['app-id']}-" \
                     f"{exc.body['call-id']}"
    except (KeyError, TypeError):
        try:
            account = request['path_params']['account']
            request_id = f"{account}-" \
                         f"{exc.body['app-id']}-" \
                         f"{exc.body['device-id']}"
        except (KeyError, TypeError):
            request_id = "unknown"

    pick_log_function(exc, task='log_request', host=host,
                      loggers=settings.params.loggers,
                      request_id=request_id, body=exc.body)

    pick_log_function(exc, task='log_failure', host=host,
                      loggers=settings.params.loggers,
                      request_id=request_id, body=exc.body,
                      error_msg=error_msg)

    content = jsonable_encoder({'code': code,
                                'description': error_msg,
                                'data': ''})

    return JSONResponse(
        status_code=status_code,
        content=content)
