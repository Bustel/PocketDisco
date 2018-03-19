let context;

let playback_start_local_time;             //Start time of very first segment in list of buffered segments
let last_seg_end_time;  //End time of last currently scheduled segment (offset from playback start time)

let isPlaying;
let isStopped;

let segment_buffer;
let segment_buffer_insert_index;

let scheduled_item_count; //number of scheduled items (including item currently being played)

const max_scheduled_items = 8;
const max_buffered_items = 8; //max. number of items to be stored locally. has to be equal to, or smaller than number of scheduled items.

const segment_list_check_interval = 3000;

window.onload = init;

function init() {
    let btnPlay = document.getElementById("play");
    btnPlay.disabled = true;

    context = new (window.AudioContext || window.webkitAudioContext)();

    isPlaying = false;
    isStopped = true;

    segment_buffer = [];
    segment_buffer_insert_index = 0;

    scheduled_item_count = 0;
}

function loadButtonTapped() {
    //Start downloader:
    let http_worker = new Worker('/static/segment_loader.js');
    http_worker.postMessage(["start", segment_list_check_interval]);
    http_worker.onmessage = function (e) {
        if (e.data[0] === "segment") {
            processNewSegment(e.data[1]);
        }
        if (e.data[0] === "gap") {
            //TODO
        }
        if (e.data[0] === "get_capacity") {
            let capacity = isPlaying ? (max_scheduled_items - scheduled_item_count) : max_buffered_items;
            http_worker.postMessage(["capacity", capacity]);
        }
    };

    let btnLoad = document.getElementById("load");
    btnLoad.disabled = true;
}

function processNewSegment(segment) {
    //Decode segment first:
    context.decodeAudioData(segment.data, function (buffer) {
        if (isPlaying) {
            console.log("processNewSegment: scheduling seq " + segment.no);
            scheduleSegment(buffer, 0);
        } else if (isStopped) {
            //Store segment for later playback:
            segment.buffer = buffer;

            let index = segment_buffer_insert_index % max_buffered_items;
            segment_buffer[index] = segment;
            segment_buffer_insert_index++;

            let btnPlay = document.getElementById("play");
            btnPlay.disabled = false;
        }
    }, function (e) {
        console.log('Failed to decode audio data', e);
        console.log(segment.data);
    });
}

function buttonTapped() {
    if (isPlaying) {
        return;
    }

    if (isStopped) {
        if (segment_buffer.length === 0) {
            console.log("Cannot start playback: empty buffer.");
            return;
        }

        const request = new XMLHttpRequest();
        request.open("post", "/api/get_current_segment", false);
        request.onload = function () {
            let resp_obj = JSON.parse(request.response);

            let seq_no = resp_obj.seg_no;
            let playback_offset = resp_obj.offset;
            let client_request_time = resp_obj.request_time;

            let client_time_offset = (new Date().getTime() - client_request_time) / 1000;
            playback_offset += client_time_offset / 2;

            console.log("Request took " + client_time_offset + " s.");
            console.log("Attempting to start playback for segment " + seq_no + " at offset " + playback_offset);

            let found_first = false;

            let max = segment_buffer_insert_index;
            let min = segment_buffer_insert_index - (max_buffered_items - 1);
            if (min < 0) {
                min = 0;
            }

            let i;
            for (i = min; i < max; i++) {
                let index = i % max_buffered_items;

                let segment = segment_buffer[index];
                if (segment.no < seq_no) {
                    console.log("Seq " + segment.no + " already played.");
                }
                else if (segment.no === seq_no) {
                    found_first = true;
                    console.log("Segment found. Scheduling for playback.");
                    scheduleSegment(segment_buffer[index].buffer, playback_offset);
                } else if (segment.no > seq_no)
                    if (!found_first) {
                        console.log("Seq " + segment.no + " for future play (not found first yet).");
                    } else {
                        scheduleSegment(segment_buffer[index].buffer, 0);
                    }
            }

            if (!found_first) {
                console.error("Requested segment with no " + seq_no + " not yet buffered.");
            }
            else {
                let btnPlay = document.getElementById("play");
                btnPlay.disabled = true;
            }
        };
        //Add content:
        let time = {};
        time.request_time = new Date().getTime();
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify(time));
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
    source.onended = function (ev) {
        scheduled_item_count--;
    };
    source.buffer = buffer;
    source.connect(context.destination);
    source.start(start_time, offset);

    last_seg_end_time += buffer.duration - offset;

    scheduled_item_count++;
}

