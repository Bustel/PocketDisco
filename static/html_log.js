let log_list = [];
const max_log_size = 5;

const enable_html_log = true;

function divLog(data) {
    if (log_list.length === max_log_size) {
        log_list.shift();
    }
    log_list.push(data);


    let divOut = document.getElementById("divOut");
    divOut.innerHTML = "";

    let i;
    for (i = 0; i < log_list.length; i++) {
        divOut.innerHTML += log_list[i];
        if (i < log_list.length - 1) {
            divOut.innerHTML += "<br/>";
        }
    }
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