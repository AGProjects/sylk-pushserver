import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from typing import Optional

from pushserver.models.requests import WakeUpRequest, PushRequest
from pushserver.resources import settings
from pushserver.resources.storage import TokenStorage
from pushserver.resources.storage.errors import StorageError
from pushserver.resources.notification import handle_request
from pushserver.resources.utils import (check_host,
                                        log_event, log_incoming_request,
                                        log_push_request,
                                        fix_platform_name)

router = APIRouter()


async def task_push(account: str,
                    push_request: PushRequest,
                    request_id: str,
                    host: str,
                    device: Optional[str] = None):

    code, description, data = '', '', []
    storage = TokenStorage()
    try:
        storage_data = storage[account]
    except StorageError:
        log_push_request(task='log_failure',
                         host=host, loggers=settings.params.loggers,
                         request_id=request_id, body=push_request.__dict__,
                         error_msg=f'500: {{\"detail\": \"{error.detail}\"}}')
        return
    expired_devices = []

    if not storage_data:
        # Push request was not sent: user not found
        storage.remove(account)
        return

    for device_key, push_parameters in storage_data.items():
        if device is not None and device != push_parameters['device_id']:
            continue

        push_parameters.update(push_request.__dict__)

        push_parameters['platform'] = fix_platform_name(push_parameters['platform'])

        reversed_push_parameters = {}
        for item in push_parameters.keys():
            value = push_parameters[item]
            if item in ('sip_to', 'sip_from'):
                item = item.split('_')[1]
            else:
                item = item.replace('_', '-')
            reversed_push_parameters[item] = value

        # Use background_token for cancel
        if push_parameters['event'] == 'cancel' and push_parameters['background_token'] is not None:
            reversed_push_parameters['token'] = push_parameters['background_token']

        try:
            wp = WakeUpRequest(**reversed_push_parameters)
        except ValidationError as e:
            error_msg = e.errors()[0]['msg']
            log_push_request(task='log_failure', host=host,
                             loggers=settings.params.loggers,
                             request_id=request_id, body=push_request.__dict__,
                             error_msg=error_msg)
            return

        log_incoming_request(task='log_success',
                             host=host, loggers=settings.params.loggers,
                             request_id=request_id, body=wp.__dict__)
        results = handle_request(wp, request_id=request_id)

        code = results.get('code')
        if code == 410:
            expired_devices.append((push_parameters['app-id'], push_parameters['device-id']))
            code = 200
        description = 'push notification responses'
        data.append(results)

    for device in expired_devices:
        msg = f'Removing {device[1]} from {account}'
        log_event(loggers=settings.params.loggers,
                  msg=msg, level='deb')
        storage.remove(account, *device)

    if code == '':
        description, data = 'Push request was not sent: device not found', {"device_id": push_parameters['device_id']}
        log_event(loggers=settings.params.loggers,
                  msg=f'{description} {data}', level='warn')
    else:
        log_event(loggers=settings.params.loggers,
                  msg=f'{description} {data}', level='deb')


@router.post('/{account}/push', response_model=PushRequest)
@router.post('/{account}/push/{device}', response_model=PushRequest)
async def push_requests(account: str,
                        request: Request,
                        push_request: PushRequest,
                        background_tasks: BackgroundTasks,
                        device: Optional[str] = None):

    host, port = request.client.host, request.client.port

    code, description, data = '', '', []

    if check_host(host, settings.params.allowed_pool):
        request_id = f"{push_request.event}-{account}-{push_request.call_id}"

        if not settings.params.return_async:
            background_tasks.add_task(log_push_request, task='log_request',
                                      host=host, loggers=settings.params.loggers,
                                      request_id=request_id, body=push_request.__dict__)
            background_tasks.add_task(log_incoming_request, task='log_success',
                                      host=host, loggers=settings.params.loggers,
                                      request_id=request_id, body=push_request.__dict__)
            background_tasks.add_task(task_push,
                                      account=account,
                                      push_request=push_request,
                                      request_id=request_id,
                                      host=host,
                                      device=device)
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
            storage = TokenStorage()
            try:
                storage_data = storage[account]
            except StorageError:
                error = HTTPException(status_code=500, detail="Internal error: storage")
                log_push_request(task='log_failure',
                                 host=host, loggers=settings.params.loggers,
                                 request_id=request_id, body=push_request.__dict__,
                                 error_msg=f'500: {{\"detail\": \"{error.detail}\"}}')
                raise error
            expired_devices = []

            log_push_request(task='log_request',
                             host=host, loggers=settings.params.loggers,
                             request_id=request_id, body=push_request.__dict__)
            if not storage_data:
                description, data = 'Push request was not sent: user not found', {"account": account}
                storage.remove(account)
                return JSONResponse(status_code=status.HTTP_404_NOT_FOUND,
                                    content={'code': 404,
                                             'description': description,
                                             'data': data})

            for device_key, push_parameters in storage_data.items():
                if device is not None and device != push_parameters['device_id']:
                    continue

                push_parameters.update(push_request.__dict__)

                push_parameters['platform'] = fix_platform_name(push_parameters['platform'])

                reversed_push_parameters = {}
                for item in push_parameters.keys():
                    value = push_parameters[item]
                    if item in ('sip_to', 'sip_from'):
                        item = item.split('_')[1]
                    else:
                        item = item.replace('_', '-')
                    reversed_push_parameters[item] = value

                # Use background_token for cancel and message
                if push_parameters['event'] in ('cancel', 'message') and push_parameters['background_token'] is not None:
                    reversed_push_parameters['token'] = push_parameters['background_token']

                try:
                    wp = WakeUpRequest(**reversed_push_parameters)
                except ValidationError as e:
                    error_msg = e.errors()[0]['msg']
                    log_push_request(task='log_failure', host=host,
                                     loggers=settings.params.loggers,
                                     request_id=request_id, body=push_request.__dict__,
                                     error_msg=error_msg)
                    content = jsonable_encoder({'code': 400,
                                                'description': error_msg,
                                                'data': ''})
                    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                        content=content)

                log_incoming_request(task='log_success',
                                     host=host, loggers=settings.params.loggers,
                                     request_id=request_id, body=wp.__dict__)
                results = handle_request(wp, request_id=request_id)

                code = results.get('code')
                if code == 410:
                    expired_devices.append((push_parameters['app-id'], push_parameters['device-id']))
                    code = 200
                description = 'push notification responses'
                data.append(results)

            for expired_device in expired_devices:
                msg = f'Removing {expired_device[1]} from {account}'
                log_event(loggers=settings.params.loggers,
                          msg=msg, level='info')
                storage.remove(account, *expired_device)

        if code == '':
            description, data = 'Push request was not sent: device not found', {"device_id": push_parameters['device_id']}
            content = {'code': 404,
                       'description': description,
                       'data': data}
            log_push_request(task='log_failure',
                             host=host, loggers=settings.params.loggers,
                             request_id=request_id, body=push_request.__dict__,
                             error_msg=f'{content}')
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND,
                                content=content)

    else:
        msg = f'incoming request from {host} is denied'
        log_event(loggers=settings.params.loggers,
                  msg=msg, level='deb')
        code = 403
        description = 'access denied by access list'
        data = {}

        log_event(loggers=settings.params.loggers,
                  sg=msg, level='deb')

    return JSONResponse(status_code=code, content={'code': code,
                                                   'description': description,
                                                   'data': data})
