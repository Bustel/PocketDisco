let timer_var = null;
let last_seq_no = -1;   //Index of last segment downloaded

const download_limit = 3;

function timer() {
    const request = new XMLHttpRequest();
    request.open("get", "/api/get_tracks", true);
    request.responseType = "json";
    request.onload = function () {
        console.log("Timer elapsed");

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


        let max = (segments.length < download_limit) ? segments.length : download_limit;

        let i;
        let prev_durations = ref_time;
        for (i = 0; i < max; i++) {
            const segment = segments[i];
            segment.start_time = prev_durations;

            const expected = last_seq_no + 1;

            if (segment.no < expected) {
                //We have already seen this segment:
                console.debug("Already have " + segment.no);
            } else if (segment.no > expected) {
                //There was a gap: stop everything
                console.error("Gap detected: expected " + expected + ", but got " + segment.no);
                last_seq_no = -1;
                stopTimer();

                postMessage(["gap"]);
                break;
            } else if (segment.no === expected) {
                //This is the next expected segment:
                console.debug("Downloading segment no. " + segment.no);
                loadSound(segment);
                last_seq_no = segment.no;
            }

            prev_durations += segments[i].duration;
        }
    };
    request.send();
}

function stopTimer() {
    if (timer_var != null) {
        clearTimeout(timer_var);
        timer_var = null;
    }
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
            stopTimer();
        }
        close();
    }
};