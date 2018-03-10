var context;

var bufferedSegments;
var currentDownloadIndex;
var currentPlaybackIndex;

var scheduleAheadTime = 0;      // How far ahead to schedule audio (sec)

var audioStartTime;             //Start time of very first segment in list of buffered segments

var isPlaying;

window.onload = init;

function init() {
    var btnPlay = document.getElementById("play");
    btnPlay.addEventListener("click", buttonTapped);

    context = new (window.AudioContext || window.webkitAudioContext)();

    currentDownloadIndex = 0;
    currentPlaybackIndex = -1;
    bufferedSegments = [];
    isPlaying = false;

    var http_worker = new Worker('/static/segment_loader.js');
    http_worker.postMessage(["start", 5000]);
    http_worker.onmessage = function (e) {
        if (e.data[0] === "segment") {
            processNewSegment(e.data[1]);
        }
        if (e.data[0] === "gap") {
            //TODO
        }
    };
}

function processNewSegment(segment) {

}

function buttonTapped() {
    if (!isPlaying) {
        var i;
        for (i = 0; i < bufferedSegments.length; i++) {
            scheduleBufferItem(i);
        }
        isPlaying = true;
    }
}

function loadSound(url) {
    var request;

    // Load the sound
    request = new window.XMLHttpRequest();
    request.open("get", url, true);
    request.responseType = "arraybuffer";
    request.onload = function () {
        context.decodeAudioData(request.response, function (buffer) {
            bufferedSegments[currentDownloadIndex] = buffer;
            currentDownloadIndex++;

            //Load next segment:
            if (currentDownloadIndex < elements.length) {
                loadSound(elements[currentDownloadIndex]);
            }

            if (isPlaying) {
                scheduleBufferItem(currentDownloadIndex - 1);
            }
        });
    };
    request.send();
}

function scheduleBufferItem(position) {
    //Sum durations of previous items:
    timeOffset = 0;
    var i;
    for (i = 0; i < position; i++) {
        timeOffset += bufferedSegments[i].duration - scheduleAheadTime;
    }

    schedulePlayback(timeOffset, bufferedSegments[position]);
}

function schedulePlayback(time, buffer) {
    var source = context.createBufferSource(); // creates a sound source
    source.buffer = buffer;                    // tell the source which sound to play
    source.connect(context.destination);       // connect the source to the context's destination (the speakers)

    if (audioStartTime == null) {
        audioStartTime = context.currentTime;
    }

    actualStartTime = audioStartTime + time;
    console.log("Scheduling audio at " + actualStartTime);

    source.start(actualStartTime);
}

