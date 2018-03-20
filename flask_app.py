import os
import time
import requests
import logging

from flask import Flask, jsonify, request, abort, render_template, send_from_directory

app = Flask(__name__)
log = logging.getLogger(__name__)

glRunning = True
PORT = 5000

audio_streams = []


def shutdown_app():
    global glRunning
    glRunning = False
    requests.post('http://localhost:%d/api/shutdown' % PORT)


def run_flask():
    app.run('0.0.0.0', PORT, use_reloader=False, threaded=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/streams')
def get_streams():
    global audio_streams
    stream_dic = {}
    stream_lst = []
    for i in range(0, len(audio_streams)):
        s = audio_streams[i]
        stream_lst.append({
            'name': s.name,
            'no': i
        })

    stream_dic['streams'] = stream_lst
    return jsonify(stream_dic)


@app.route('/api/streams/<int:stream_id>/get_tracks')
def stream_get_tracks(stream_id):
    global audio_streams
    if stream_id > len(audio_streams):
        abort(404)

    s = audio_streams[stream_id]
    with s.segment_lock:
        tracklist = {
            'segments': s.segments
        }
        return jsonify(tracklist)


@app.route('/api/streams/<int:stream_id>/get_current_segment', methods=['POST'])
def stream_get_current_segment(stream_id):
    js = request.get_json()

    global audio_streams
    s = audio_streams[stream_id]

    with s.segment_lock:
        if s.reference is None:
            s.reference = time.time()
            log.debug('Set reference to %f', s.reference)

        prev_dur = s.reference
        local_time = time.time()

        log.debug('local time: %f', local_time)

        cur_seg = None
        start_time = None
        for seg in s.segments:
            start_time = prev_dur
            end_time = start_time + seg['duration']

            log.debug('Start %f End %f', start_time, end_time)

            if start_time <= local_time < end_time:
                cur_seg = seg
                log.debug('Found current segment: %s', cur_seg)
                break
            prev_dur += seg['duration']

        if cur_seg is None:
            log.error('Could not determine current segment. local time: %f, last segment ends %f', local_time, prev_dur)
            abort(500)

        offset = local_time - start_time

        js['offset'] = offset
        js['seg_no'] = cur_seg['no']

        return jsonify(js)


@app.route('/api/get_tracks')
def api_endpoint():
    return stream_get_tracks(0)


@app.route('/api/get_current_segment', methods=['POST'])
def get_current_segment():
    return stream_get_current_segment(0)


@app.route('/segments/<path:segment>')
def serve_segments(segment):
    location = os.path.join('segments', segment)
    if not os.path.isfile(location):
        log.error('Requested segment %s does not exist.', segment)

    return send_from_directory('segments', segment, cache_timeout=1)


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
