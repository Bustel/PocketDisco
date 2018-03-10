let context;

let playback_start_local_time;             //Start time of very first segment in list of buffered segments
let last_seg_end_time;  //End time of last currently scheduled segment (offset from playback start time)

let isPlaying;
let isWaiting;
let isStopped;

let buffer = null;

window.onload = init;

function init() {
    let btnPlay = document.getElementById("play");
    btnPlay.addEventListener("click", buttonTapped);

    context = new (window.AudioContext || window.webkitAudioContext)();

    isPlaying = false;
    isWaiting = false;
    isStopped = true;

    buffer = new Ringbuffer(5);

    let http_worker = new Worker('/static/segment_loader.js');
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
    if (isPlaying) {
        buffer.store(segment);
        scheduleSegment(segment, 0);

    } else if (isWaiting) {
        let offset = get_offset(segment);

        if (offset === -1) {
            console.info("Segment with no. " + segment.no + " has already been played by other clients.");
            return;
        }

        //Play segment
        buffer.store(segment);
        scheduleSegment(segment, offset);

    } else if (isStopped) {
        buffer.store(segment);
    }

}

function get_offset(segment) {
    let seg_end_time = segment.start_time + segment.duration * 1000;
    let now = (new Date()).getTime();

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
        //Find first segment + start at offset. Then, schedule all other elements in buffer:

        let found_first = false;
        let index = 0;
        let segment = buffer.peek(index);
        while (segment != null) {
            let offset = (!found_first) ? get_offset(segment) : 0;
            if (offset === -1) {
                buffer.get(); //Already played: skip element
            }
            else {
                found_first = true;
                scheduleSegment(segment, offset);
                index++;
            }
            segment = buffer.peek(index);
        }
    }
}

function scheduleSegment(segment, offset) {
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

    schedulePlayback(start_time, offset, segment);

    last_seg_end_time += segment.duration - offset;
}


function schedulePlayback(time, offset, segment) {
    let source = context.createBufferSource(); // creates a sound source
    source.buffer = segment.buffer;                    // tell the source which sound to play
    source.connect(context.destination);       // connect the source to the context's destination (the speakers)

    source.onended = function (ev) {
        buffer.get();

        if (buffer.get_length() === 0) {
            isWaiting = true;
        }
    };

    console.log("Scheduling segment no. " + segment.no + " at " + time);

    source.start(time, offset);
}

