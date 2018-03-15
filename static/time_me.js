function time() {
    let time = {"local_time": new Date().getTime()};

    const request = new XMLHttpRequest();
    request.open("post", "/api/timesync", true);
    request.responseType = "json";
    request.onload = function () {
        let server_time = request.response.server_time;
        let server_offset = request.response.offset;
        let local_time = request.response.local_time;
        let local_offset = new Date().getTime() - local_time;

        console.log("Time at server: " + server_time);
        console.log("Received offset: " + server_offset);
        console.log("Network delay (local offset): " + local_offset);
    };
    request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    request.send(JSON.stringify(time));
}

window.onload = function () {
    setInterval(time, 1000);
};

