let context;

let playback_start_local_time;             //Start time of very first segment in list of buffered segments
let last_seg_end_time;  //End time of last currently scheduled segment (offset from playback start time)

let isPlaying;
let isStopped;

let segmentBuffer;
let prodIndex; //index of lastly produced item
let consIndex; //index of lastly consumed item

window.onload = init;

function init() {
    let btnPlay = document.getElementById("play");
    btnPlay.disabled = true;

    context = new (window.AudioContext || window.webkitAudioContext)();

    isPlaying = false;
    isStopped = true;

    segmentBuffer = [];
    prodIndex = -1;
    consIndex = 0;
}

function loadButtonTapped() {
    //Start downloader:
    let http_worker = new Worker('/static/segment_loader.js');
    http_worker.postMessage(["start", 3000]);
    http_worker.onmessage = function (e) {
        if (e.data[0] === "segment") {
            processNewSegment(e.data[1]);
        }
        if (e.data[0] === "gap") {
            //TODO
        }
    };

    let btnLoad = document.getElementById("load");
    btnLoad.disabled = true;
}

function processNewSegment(segment) {
    //Decode segment first:
    context.decodeAudioData(segment.data, function (buffer) {
        let now = (new Date()).getTime() / 1000; //need seconds

        console.log("processNewSegment: seq " + segment.no + " started at " + segment.start_time + " now is " + now);

        if (isPlaying) {
            console.log("processNewSegment: scheduling seq " + segment.no);
            scheduleSegment(buffer, 0);
        } else if (isStopped) {
            //Store segment for later playback:
            segment.buffer = buffer;

            prodIndex++;
            segmentBuffer[prodIndex] = segment;

            let btnPlay = document.getElementById("play");
            btnPlay.disabled = false;
        }
    });

}

function get_offset(segment) {
    let seg_end_time = segment.start_time + segment.duration;
    let now = (new Date()).getTime() / 1000; //need seconds

    console.log("get_offset: segment " + segment.no + " from " + segment.start_time + " to " + seg_end_time);

    if (now < segment.start_time) {
        return -2;
    }
    if (now >= seg_end_time) {
        return -1;
    }

    return now - segment.start_time;
}

function buttonTapped() {
    if (isPlaying) {
        return;
    }

    if (isStopped) {
        if (prodIndex === -1) {
            console.warn("No segments yet.");
            return;
        }

        let found_first = false;
        let index;
        let maxProd = prodIndex; //copy value to account for parallel access
        for (index = consIndex; index <= maxProd; index++) {
            let offset = get_offset(segmentBuffer[index]);
            if (offset === -1) {
                delete segmentBuffer[index];
                continue; //Already played
            } else if (offset === -2) {
                offset = 0; //Segment upcoming
            } else {
                found_first = true;
            }

            console.log("buttonTapped: scheduling " + segmentBuffer[index].no + " at " + offset);

            scheduleSegment(segmentBuffer[index].buffer, offset);
            delete segmentBuffer[index];
            consIndex = index;
        }

        if (!found_first) {
            console.warn("All segments in buffer have already been played.");
        }
        let btnPlay = document.getElementById("play");
        btnPlay.disabled = true;
    }
}

function scheduleSegment(buffer, offset) {
    let start_time;

    if (isStopped) {
        //Just starting playback:
        playback_start_local_time = context.currentTime;
        last_seg_end_time = 0;

        start_time = 0;
    }
    else {
        start_time = playback_start_local_time + last_seg_end_time
    }

    //Update state:
    isPlaying = true;
    isStopped = false;

    //Prepare playback:
    let source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    source.start(start_time, offset);

    last_seg_end_time += buffer.duration - offset;
}

