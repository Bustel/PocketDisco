import time

import math
from flask import Flask, render_template, Response

app = Flask(__name__)

times = [3.000979, 3.000000, 3.000000, 3.000000, 3.000000, 3.000000, 3.000000, 2.741417]
seq_no = 0
ref_time = -1


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/reset')
def api_reset():
    global seq_no, ref_time
    seq_no = 0
    ref_time = -1
    return ''


@app.route('/api/get_tracks')
def api_endpoint():
    global ref_time, seq_no
    if ref_time == -1:
        ref_time = time.time()

    passed = time.time() - ref_time
    if passed >= 2:
        seq_no += 1

    if seq_no >= len(times):
        sample_file = '{'
        sample_file += '"segments": []'
        sample_file += '}'
    else:
        segment_offset = 0
        for i in range(0, seq_no):
            segment_offset += times[i]

        m_segment_time = math.floor((ref_time + segment_offset) * 1000)

        sample_file = "{"
        sample_file += '"reference": "' + str(m_segment_time) + '",'
        sample_file += '"segments": ['

        max = seq_no + 3 if seq_no + 3 < len(times) else len(times)

        for i in range(seq_no, max):
            sample_file += '{"no": ' + str(i) + ','
            sample_file += '"duration": ' + "{0:.3f}".format(times[i]) + ' ,'
            sample_file += '"url": "static/media/out00' + str(i) + '.wav"}'
            if i < max - 1:
                sample_file += ','
        sample_file += ']}'

    return Response(sample_file, mimetype='application/json')


# No cacheing at all for API endpoints.
@app.after_request
def add_header(response):
    # response.cache_control.no_store = True
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'
    return response


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
