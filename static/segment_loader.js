let last_seq_no = -1;   //Index of last segment downloaded

let is_active = false;
let timeout_handle = null;
let interval;

function loadSegments(max_segments) {
    const request = new XMLHttpRequest();
    request.open("get", "/api/get_tracks", true);
    request.responseType = "json";
    request.onload = function () {

        const segments = request.response.segments;

        if (segments.length === 0) {
            console.info("Empty segment list.");
            stopTimer();
            return;
        }

        //{ no: 0, duration: 2.0004, url: "http://test/location" }
        if (last_seq_no === -1) {
            //Init seq no. counter:
            last_seq_no = segments[0].no - 1;
        }

        let i;
        let downloaded = 0;
        for (i = 0; i < segments.length; i++) {
            const segment = segments[i];
            const expected = last_seq_no + 1;

            if (segment.no < expected) {
                //We have already seen this segment:
                console.info("Already have " + segment.no);
            } else if (segment.no > expected) {
                //There was a gap: stop everything
                warn("Gap detected: expected " + expected + ", but got " + segment.no);
                last_seq_no = -1;
                postMessage(["gap"]);
                stopTimer();
                return;
            } else if (segment.no === expected) {
                //This is the next expected segment:
                console.debug("Downloading segment no. " + segment.no);
                loadSound(segment);
                downloaded++;
                last_seq_no = segment.no;

                if ((downloaded === max_segments) && (i < segments.length - 1)) {
                    warn("Max. number of segments reached. Ignoring remaining segments.");
                    break;
                }
            }
        }

        //re-schedule function:
        timeout_handle = setTimeout(timer, interval);
    };
    request.send();
}

function timer() {
    log("Timer elapsed");
    timeout_handle = null;

    //Ask main script for number of segments we can download:
    postMessage(["get_capacity"]);
}


function loadSound(segment) {
    const request = new XMLHttpRequest();
    request.open("get", segment.url, false);
    request.responseType = "arraybuffer";
    request.onload = function () {
        if (request.status === 200) {
            segment.data = request.response;

            if (segment.data.byteLength === 0) {
                warn('Trying to pass empty segment data to Decoder')
            } else {
                log(segment.data.byteLength)
            }

            postMessage(["segment", segment]);
        } else {
            log('Segment request failed', request.response)
        }

    };
    request.send();
}

function stopTimer() {
    log("Stopping timer.");
    is_active = false;

    if (timeout_handle != null) {
        clearTimeout(timeout_handle); //clear pending requests
    }

    close(); //kill the web worker
}

onmessage = function (event) {
    if ((event.data[0] === "start") && (is_active === false)) {
        is_active = true;

        interval = event.data[1];
        log("Starting timer. Interval = " + interval);
        timer(); //immediately execute first call
    }
    if (event.data[0] === "stop" && (is_active === true)) {
        stopTimer();
    }
    if (event.data[0] === "capacity") {
        max_segments = event.data[1];
        loadSegments(max_segments);
    }
};