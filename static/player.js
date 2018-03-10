let context;

let playback_start_local_time;             //Start time of very first segment in list of buffered segments
let last_seg_end_time;  //End time of last currently scheduled segment (offset from playback start time)

let isPlaying;
let isWaiting;
let isStopped;

let buffer = null;
let consumer;
let producer;
const buffer_capacity = 5;

window.onload = init;

function init() {
    let btnPlay = document.getElementById("play");
    btnPlay.addEventListener("click", buttonTapped);

    context = new (window.AudioContext || window.webkitAudioContext)();

    isPlaying = false;
    isWaiting = false;
    isStopped = true;

    buffer = [];
    consumer = -1;
    producer = -1;
}

function store_segment(segment) {
    producer++;
    buffer[producer % buffer_capacity] = segment;
}

function get_segment(index) {
    if (index === -1) {
        return null;
    }
    return buffer[index % buffer_capacity];
}

function processNewSegment(segment) {
    //Decode segment first:
    context.decodeAudioData(segment.data, function (buffer) {
        segment.buffer = buffer;

        if (isPlaying) {
            store_segment(segment);
            scheduleSegment(producer, 0);

        } else if (isWaiting) {
            let offset = get_offset(segment);

            if (offset === -1) {
                console.info("Segment with no. " + segment.no + " has already been played by other clients.");
                return;
            }

            //Play segment
            store_segment(segment);
            scheduleSegment(producer, 0);

        } else if (isStopped) {
            store_segment(segment);
        }
    });

}

function get_offset(segment) {
    let seg_end_time = segment.start_time + segment.duration;
    let now = (new Date()).getTime() / 1000; //need seconds

    if ((now < segment.start_time) || (now >= seg_end_time)) {
        return -1;
    }
    return now - segment.start_time;
}

function buttonTapped() {
    if (isPlaying || isWaiting) {
        return;
    }

    if (isStopped) {
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

        isWaiting = true;
        isStopped = false;
    }

    // if (isStopped) {
    //     //Find first segment + start at offset. Then, schedule all other elements in buffer:
    //
    //     let found_first = false;
    //     let index = 0;
    //     let segment = buffer.peek(index);
    //     while (segment != null) {
    //         let offset = (!found_first) ? get_offset(segment) : 0;
    //         if (offset === -1) {
    //             buffer.get(); //Already played: skip element
    //         }
    //         else {
    //             found_first = true;
    //             scheduleSegment(segment, offset);
    //             index++;
    //         }
    //         segment = buffer.peek(index);
    //     }
    //
    //     if (!found_first) {
    //         console.warn("All segments in buffer have already been played.");
    //         isWaiting = true;
    //     }
    // }
}

function scheduleSegment(index, offset) {
    let start_time;

    if (isStopped || isWaiting) {
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
    isWaiting = false;

    //Prepare playback:
    let source = context.createBufferSource();
    source.buffer = get_segment(index).buffer;
    source.connect(context.destination);
    source.start(start_time, offset);

    last_seg_end_time += get_segment(index).duration - offset;
}

function loadSound(url) {
    var request;

    // Load the sound
    request = new window.XMLHttpRequest();
    request.open("get", url, true);
    request.responseType = "arraybuffer";
    request.onload = function () {
        let segment = {};
        segment.data = request.response;
        processNewSegment(segment);
    };
    request.send();
}

function schedulePlayback(time, offset, index) {


    // source.onended = function (ev) {
    //     consumer++;
    //
    //     if (consumer === producer) {
    //         console.info("Cannot continue playback: buffer empty.");
    //         isWaiting = true;
    //     }
    // };

    console.info("Scheduling segment no. " + segment.no + " at " + time + " [offset = " + offset + "]");

    source.start(0);
}

