import asyncio
import os

from typing import Callable

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pushserver.api.errors.validation_error import validation_exception_handler
from pushserver.api.routes.api import router
from pushserver.resources import settings
from pushserver.resources.utils import log_event


def get_server() -> FastAPI:
    server = FastAPI(title='sylk-pushserver', version='1.0.0', debug=True)
    server.add_event_handler("startup", create_start_server_handler())
    server.add_exception_handler(RequestValidationError, validation_exception_handler)
    server.include_router(router)

    return server


async def autoreload_read_config(wait_for: float = 0.1) -> None:
    """
    Set global parameters when config folder changes.
    :param wait_for: `float` time to sleep between looks for changes.
    """
    # thanks to lbellomo for the concept of this function

    to_watch = {}
    paths_list = [settings.params.file['path'],
                  settings.params.apps['path'],
                  settings.params.apps['credentials']]
    for path in paths_list:
        try:
            to_watch[path] = os.stat(path).st_mtime
        except FileNotFoundError:
            pass

    while True:
        for path in to_watch.keys():
            last_st_mtime = to_watch[path]
            path_modified = last_st_mtime != os.stat(path).st_mtime
            if path_modified:
                to_watch[path] = os.stat(path).st_mtime
                settings.params = settings.update_params(settings.params.config_dir,
                                                         settings.params.debug,
                                                         settings.params.ip,
                                                         settings.params.port)
                await asyncio.sleep(wait_for)
                break
            await asyncio.sleep(wait_for)


def create_start_server_handler() -> Callable:  # type: ignore
    wait_for = 0.1

    async def start_server() -> None:

        asyncio.create_task(autoreload_read_config(wait_for=wait_for))

        level = 'info'
        loggers = settings.params.loggers
        register = settings.params.register

        pns_register = register['pns_register']
        msg = f"Loaded {len(pns_register)} applications from " \
              f"{settings.params.apps['path']}:"
        log_event(loggers=loggers, msg=msg, level=level)

        for app in pns_register.keys():
            app_id, platform = app
            name = pns_register[app]['name']
            msg = f"Loaded {platform.capitalize()} "\
                  f"{name.capitalize()} app {app_id}" \

            log_event(loggers=loggers, msg=msg, level=level)

            if settings.params.loggers['debug']:
                headers_class = pns_register[app]['headers_class']
                payload_class = pns_register[app]['payload_class']

                msg = f"{name.capitalize()} app {app_id} classes: " \
                      f"{headers_class.__name__}, {payload_class.__name__}"
                log_event(loggers=loggers, msg=msg, level='deb')

                log_remote = pns_register[app]['log_remote']
                if log_remote['error']:
                    msg = f"{name.capitalize()} loading of log remote settings failed: " \
                          f"{log_remote['error']}"
                    log_event(loggers=loggers, msg=msg, level='deb')
                elif log_remote.get('log_remote_urls'):
                    log_settings = ''
                    for k, v in log_remote.items():
                        if k == 'error':
                            continue
                        if k == 'log_urls':
                            v = ', '.join(v)
                        if k == 'log_remote_key' and not v:
                            continue
                        if k == 'log_remote_timeout' and not v:
                            continue
                        log_settings += f'{k}: {v} '
                    msg = f'{name.capitalize()} log remote settings: {log_settings}'
                    log_event(loggers=loggers, msg=msg, level='deb')

        invalid_apps = register['invalid_apps']
        for app in invalid_apps.keys():
            app_id, platform = app[0], app[1]
            name = invalid_apps[app]['name']
            reason = invalid_apps[app]['reason']
            msg = f"{name.capitalize()} app with {app_id} id for {platform} platform " \
                  f"will not be available, reason: {reason}"
            log_event(loggers=loggers, msg=msg, level=level)

        pnses = register['pnses']

        if settings.params.loggers['debug']:
            level = 'deb'
            msg = f'Loaded {len(pnses)} Push notification services: ' \
                  f'{", ".join(pnses)}'
            log_event(loggers=loggers, msg=msg, level=level)

            for pns in pnses:
                msg = f"{pns.split('PNS')[0]} Push Notification Service - " \
                      f"{pns} class"
                log_event(loggers=loggers, msg=msg, level=level)

        if settings.params.allowed_pool:
            nets = [net.with_prefixlen for net in settings.params.allowed_pool]
            msg = f"Allowed hosts: " \
                  f"{', '.join(nets)}"
            log_event(loggers=loggers, msg=msg, level=level)

        if settings.params.loggers['debug']:
            msg = 'Server is now ready to answer requests'
            log_event(loggers=loggers, msg=msg, level='deb')

        ip, port = settings.params.server['host'], settings.params.server['port']
        msg = f'Sylk Pushserver listening on http://{ip}:{port}'
        log_event(loggers=loggers, msg=msg, level='info')

        await asyncio.sleep(wait_for)

    return start_server


server = get_server()
