let context;

let playback_start_local_time;             //Start time of very first segment in list of buffered segments
let last_seg_end_time;  //End time of last currently scheduled segment (offset from playback start time)

let isPlaying;
let isWaiting;
let isStopped;

let buffer;
let bufferIndex;

window.onload = init;

function init() {
    context = new (window.AudioContext || window.webkitAudioContext)();

    isPlaying = false;
    isWaiting = false;
    isStopped = true;

    buffer = [];
    bufferIndex = 0;
}

function processNewSegment(segment) {
    //Decode segment first:
    context.decodeAudioData(segment.data, function (buffer) {
        let now = (new Date()).getTime() / 1000; //need seconds
        console.log("seq " + segment.no + " started at " + segment.start_time + " now is " + now);
        let seg_end_time = segment.start_time + segment.duration;
        console.log("Segment " + segment.no + " from " + segment.start_time + " to " + seg_end_time);



        if (isPlaying) {
            scheduleSegment(buffer, 0);

        } else if (isWaiting) {
            let offset = get_offset(segment);


            if (offset === -1) {
                console.info("Segment no. " + segment.no + " has already been played by other clients.");
                return;
            }

            if (offset === -2) {
                console.info("Received segment " + segment.no + " not awaited one.");
                return; //Segment not ready for playback yet
            }

            //Play segment:
            console.info("Scheduling segment " + segment.no + " at " + offset);
            scheduleSegment(buffer, offset);

        } else if (isStopped) {
            //Store segment for later playback:
            segment.buffer = buffer;
            buffer[bufferIndex] = segment;
            bufferIndex++;
        }
    });

}

function get_offset(segment) {
    let seg_end_time = segment.start_time + segment.duration;
    let now = (new Date()).getTime() / 1000; //need seconds

    console.log("Segment " + segment.no + " from " + segment.start_time + " to " + seg_end_time);

    if (now < segment.start_time) {
        return -2;
    }
    if (now >= seg_end_time) {
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

function scheduleSegment(buffer, offset) {
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
    source.buffer = buffer;
    source.connect(context.destination);
    source.start(start_time, offset);

    last_seg_end_time += buffer.duration - offset;
}

