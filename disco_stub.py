from flask import Flask, render_template, Response

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/get_tracks')
def api_endpoint():
    sample_file = "{"
    sample_file += '"reference": "1500000",'
    sample_file += '"segments": ['

    for i in range(0, 3):
        sample_file += '{"no": ' + str(i) + ','
        sample_file += '"duration": 2.0004,'
        sample_file += '"url": "http://test/location"}'
        if i < 2:
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
