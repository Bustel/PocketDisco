var timer_var = null;

function timer() {
    var request = new XMLHttpRequest();
    request.open("get", "/api/get_tracks", true);
    request.responseType = "json";
    request.onload = function () {
        var ref_time = request.response.reference;
        var segments = request.response.segments;

        postMessage([ref_time, segments]);
    };
    request.send();
}

onmessage = function (event) {
    console.log('Message received from main script');

    if ((event.data[0] === 'start') && (timer_var == null)) {
        interval = event.data[1];
        console.log("Timer started. Interval = " + interval);
        timer_var = setInterval(function () {
            timer()
        }, interval);
    }
    if (event.data[0] === 'stop') {
        console.log("Timer stopped");
        if (timer_var != null) {
            clearTimeout(timer_var);
            timer_var = null;
        }
        close();
    }

    //
    // var workerResult = 'Result: ' + (e.data[0] * e.data[1]);
    //
    // console.log('Posting message back to main script');
    // postMessage(workerResult);
};