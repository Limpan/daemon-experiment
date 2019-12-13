#!/usr/bin/env python3
from threading import Event, Thread
from werkzeug.wrappers import Request as _Request, Response as _Response
from werkzeug.wrappers.json import JSONMixin
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import abort, HTTPException, NotFound
import time
import logging
import arrow
import json


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()


class Request(JSONMixin, _Request):
    pass


class Response(JSONMixin, _Response):
    pass


class BackgroundThread(Thread):
    def __init__(self, stop_event, *args, **kwargs):
        self.stop_event = stop_event
        Thread.__init__(self, *args, **kwargs)
        self.count = 0

    def run(self):
        logger.info('Thread starting...')

        while not stop_event.wait(1):
            self.count += 1
            logger.info('Count: {}'.format(self.count))

        logger.info('Stopping background thread.')


class Server(object):
    def __init__(self, config):
        self.url_map = Map([
            Rule('/', endpoint='create'),
            Rule('/status', endpoint='status'),
        ])

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        headers = [('Content-Type', 'application/json'),
                   ('Cache-Control', 'max-age=0, private, must-revalidate'),
                   ('X-Content-Type-Options', 'nosniff'),
            ]
        try:
            endpoint, values = adapter.match()
            body = getattr(self, 'on_' + endpoint)(request, **values)
            return Response(json.dumps(body), headers=headers)
        except HTTPException as e:
            body = json.dumps({'message': e.description,
                               'error': e.code})
            return Response(body, status=e.code, headers=headers)

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def on_status(self, request):
        return {'data': 'Online'}

    def on_create(self, request):
        error = None
        if not request.method == 'POST':
            abort(403)
        if not request.is_json:
            abort(401)

        return {'message': 'resource created', 'data': 'xyz123'}


def create_app():
    app = Server({})
    return app




if __name__ == "__main__":
    logger.info('Starting daemon.')
    stop_event = Event()
    background_thread = BackgroundThread(stop_event)
    background_thread.start()

    logger.info('Starting API-server.')
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('127.0.0.1', 5000, app)
