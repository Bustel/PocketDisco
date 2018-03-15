function time() {
    let time = {"local_time": new Date().getTime()};

    const request = new XMLHttpRequest();
    request.open("post", "/api/timesync", true);
    request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    request.send(JSON.stringify(time));
}

window.onload = function () {
    setInterval(time, 1000);
};

