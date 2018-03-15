import os
import time
import requests


from flask import Flask, jsonify, request, abort, send_file, render_template

app = Flask(__name__)

glRunning = True
PORT = 5000

audio_streams = []


def shutdown_app():
    global glRunning
    glRunning = False
    requests.post('http://localhost:%d/api/shutdown' % PORT)


def run_flask():
    app.run('0.0.0.0', PORT, use_reloader=False)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/timesync', methods=['POST'])
def time_sync():
    js = request.get_json()
    time_utc = js['local_time']
    my_time = time.time()*1000
    offset = my_time - time_utc

    resp = {
        'local_time': time_utc,
        'server_time': my_time,
        'offset': offset
    }

    print('server_time', my_time)
    print('local_time', time_utc)
    print('Offset', offset)

    return jsonify(resp)


@app.route('/api/get_tracks')
def api_endpoint():
    global audio_streams
    s = audio_streams[0]

    with s.segment_lock:
        if s.reference is None:
            s.reference = time.time()

        tracklist = {
            'reference': s.reference,
            'segments': s.segments
        }
        return jsonify(tracklist)


@app.route('/segments/<path:segment>')
def serve_segments(segment):
    return send_file(os.path.join('segments', segment), cache_timeout=1)


@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    if not glRunning:
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return 'Server shutting down...'
    else:
        abort(404)


# No cacheing at all for API endpoints.
@app.after_request
def add_header(response):
    # response.cache_control.no_store = True
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'
    return response
