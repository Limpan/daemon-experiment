#!/usr/bin/env python3
import threading, queue
from werkzeug.wrappers import Request as _Request, Response as _Response
from werkzeug.wrappers.json import JSONMixin
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import abort, HTTPException, NotFound
import time
import logging
import arrow
import json


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


MODE_STATIC = 1
MODE_CLOCK = 2
MODE_TIMER = 3


config = {'NUM_LEDS': 60}


class Request(JSONMixin, _Request):
    pass


class Response(JSONMixin, _Response):
    pass


class Daemon(threading.Thread):
    def __init__(self, config, stop_event, command_queue, *args, **kwargs):
        self.stop_event = stop_event
        self.command_queue = command_queue
        threading.Thread.__init__(self, *args, **kwargs)
        self.count = 0

        self.mode = MODE_STATIC
        self.timer = []

    def run(self):
        logger.info('Thread starting...')

        while not stop_event.wait(0.05):
            self.count += 1
            # logger.debug('Count: {}'.format(self.count))
            if not self.command_queue.empty():
                self.process_command(self.command_queue.get())
        logger.info('Stopping background thread.')

    def process_command(self, cmd):
        logger.info('Processing command: {}'.format(cmd))


class Server(object):
    def __init__(self, config, background_thread, command_queue):
        self.background_thread = background_thread
        self.messages = command_queue
        self.url_map = Map([
            Rule('/', endpoint='index'),
            Rule('/led', endpoint='led'),
            Rule('/mode', endpoint='mode'),
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

    def on_index(self, request):
        return {'data': 'Online'}

    def on_led(self, request):
        error = None
        if not request.method == 'POST':
            abort(403)
        if not request.is_json:
            abort(401)

        return {'message': 'resource created', 'data': 'xyz123'}

    def on_mode(self, request):
        self.messages.put({'command': 'mode'})
        return {'message': 'clock'}


def create_app(background_thread, command_queue):
    app = Server(config, background_thread, command_queue)
    return app


logger.info('Starting daemon.')
stop_event = threading.Event()
command_queue = queue.Queue()
# mutex = threading.Lock()
daemon = Daemon(config, stop_event, command_queue)
daemon.start()

logger.info('Starting API-server.')
from werkzeug.serving import run_simple
app = create_app(daemon, command_queue)

if __name__ == "__main__":
    run_simple('127.0.0.1', 5000, app)
