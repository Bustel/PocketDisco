const enable_html_log = true;

function divLog(data) {
    document.getElementById("divLog").innerHTML += data + "<br/>";
}

function error(data) {
    console.error(data);

    if (enable_html_log) {
        divLog("ERROR: " + data);
    }
}

function warn(data) {
    console.warn(data);
    if (enable_html_log) {
        divLog("WARNING: " + data);
    }
}

function log(data) {
    console.log(data);
    if (enable_html_log) {
        divLog(data);
    }
}