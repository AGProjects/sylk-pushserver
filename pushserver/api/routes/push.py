import json

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from pushserver.models.requests import WakeUpRequest, fix_platform_name
from pushserver.resources import settings
from pushserver.resources.notification import handle_request
from pushserver.resources.utils import (check_host,
                                        log_event, log_incoming_request)

router = APIRouter()


@router.post('', response_model=WakeUpRequest)
async def push_requests(request: Request,
                        wp_request: WakeUpRequest,
                        background_tasks: BackgroundTasks):

    wp_request.platform = fix_platform_name(wp_request.platform)

    host, port = request.client.host, request.client.port

    code, description, data = '', '', {}

    if check_host(host, settings.params.allowed_pool):
        request_id = f"{wp_request.event}-{wp_request.app_id}-{wp_request.call_id}"

        if not settings.params.return_async:
            background_tasks.add_task(log_incoming_request, task='log_request',
                                      host=host, loggers=settings.params.loggers,
                                      request_id=request_id, body=wp_request.__dict__)

            background_tasks.add_task(log_incoming_request, task='log_success',
                                      host=host, loggers=settings.params.loggers,
                                      request_id=request_id, body=wp_request.__dict__)
            background_tasks.add_task(handle_request,
                                      wp_request=wp_request,
                                      request_id=request_id)
            status_code, code = status.HTTP_202_ACCEPTED, 202
            description, data = 'accepted for delivery', {}

            try:
                return JSONResponse(status_code=status_code,
                                    content={'code': code,
                                             'description': description,
                                             'data': data})
            except json.decoder.JSONDecodeError:
                return JSONResponse(status_code=status_code,
                                    content={'code': code,
                                             'description': description,
                                             'data': {}})

        else:
            log_incoming_request(task='log_request',
                                 host=host, loggers=settings.params.loggers,
                                 request_id=request_id, body=wp_request.__dict__)

            log_incoming_request(task='log_success',
                                 host=host, loggers=settings.params.loggers,
                                 request_id=request_id, body=wp_request.__dict__)
            results = handle_request(wp_request, request_id=request_id)
            code = results.get('code')
            description = 'push notification response'
            data = results

    else:
        msg = f'incoming request from {host} is denied'
        log_event(loggers=settings.params.loggers,
                  msg=msg, level='deb')
        code = 403
        description = 'access denied by access list'
        data = {}

        log_event(loggers=settings.params.loggers,
                  msg=msg, level='deb')

    return JSONResponse(status_code=code, content={'code': code,
                                                   'description': description,
                                                   'data': data})
