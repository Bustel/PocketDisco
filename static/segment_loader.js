let last_seq_no = -1;   //Index of last segment downloaded

let is_active = false;
let timeout_handle = null;
let interval;

const download_limit = 3;

function timer() {
    console.log("Timer elapsed");
    timeout_handle = null;

    const request = new XMLHttpRequest();
    request.open("get", "/api/get_tracks", true);
    request.responseType = "json";
    request.onload = function () {

        const ref_time = request.response.reference;
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
        let prev_durations = ref_time;

        let downloaded = 0;
        for (i = 0; i < segments.length; i++) {
            const segment = segments[i];
            const expected = last_seq_no + 1;

            segment.start_time = prev_durations;
            if (segment.no < expected) {
                //We have already seen this segment:
                console.info("Already have " + segment.no);
            } else if (segment.no > expected) {
                //There was a gap: stop everything
                console.warn("Gap detected: expected " + expected + ", but got " + segment.no);
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

                if (downloaded === max) {
                    console.info("Download limit reached: processed " + downloaded + " of " + segments.length);
                    break;
                }

            }
            prev_durations += segments[i].duration;
        }

        //re-schedule function:
        timeout_handle = setTimeout(timer, interval);
    };
    request.send();
}


function loadSound(segment) {
    const request = new XMLHttpRequest();
    request.open("get", segment.url, false);
    request.responseType = "arraybuffer";
    request.onload = function () {
        segment.data = request.response;
        postMessage(["segment", segment]);
    };
    request.send();
}

function stopTimer() {
    console.log("Stopping timer.");
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
        console.log("Starting timer. Interval = " + interval);
        timer(); //immediately execute first call
    }
    if (event.data[0] === "stop" && (is_active === true)) {
        stopTimer();
    }
};