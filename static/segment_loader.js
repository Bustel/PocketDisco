var timer_var = null;
var last_seq_no = -1;

function timer() {
    var request = new XMLHttpRequest();
    request.open("get", "/api/get_tracks", true);
    request.responseType = "json";
    request.onload = function () {
        var ref_time = request.response.reference;
        var segments = request.response.segments;

        if (segments.length === 0) {
            return;
        }

        //{ no: 0, duration: 2.0004, url: "http://test/location" }

        //Check seq no of first element:
        if (last_seq_no === -1) {
            last_seq_no = segments[0].no - 1;
        }

        var i;
        var prev_durations = ref_time;
        for (i = 0; i < segments.length; i++) {
            var segment = segments[i];
            segment.start_time = prev_durations;

            if (segment.no >= last_seq_no + 1) {
                loadSound(segment);
                last_seq_no = segment.no;
            }

            prev_durations += segments[i].duration;
        }
    };
    request.send();
}

function loadSound(segment) {
    var request = new XMLHttpRequest();
    request.open("get", segment.url, false);
    request.responseType = "arraybuffer";
    request.onload = function () {
        context.decodeAudioData(request.response, function (buffer) {
            segment.buffer = buffer;
            postMessage(segment);
        });
    };
    request.send();
}

onmessage = function (event) {
    if ((event.data[0] === "start") && (timer_var == null)) {
        interval = event.data[1];
        console.log("Starting timer. Interval = " + interval);
        timer_var = setInterval(function () {
            timer()
        }, interval);
    }
    if (event.data[0] === "stop") {
        console.log("Stopping timer.");
        if (timer_var != null) {
            clearTimeout(timer_var);
            timer_var = null;
        }
        close();
    }
};