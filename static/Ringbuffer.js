class Ringbuffer {
    storage;
    capacity;

    current_consumer;
    current_producer;

    constructor(capacity) {
        this.capacity = capacity;
        this.storage = [];

        this.current_consumer = -1;
        this.current_producer = -1;
    }

    get_length() {
        return this.current_producer - this.current_consumer;
    }

    peek(offset) {
        let consumer_index = this.current_consumer + 1 + offset;

        if (this.current_producer < consumer_index) {
            //Item at index has not been produced yet:
            return null;
        }

        let index = consumer_index % this.capacity;
        return this.storage[index];
    }

    get() {
        this.current_consumer++;

        if (this.current_producer < this.current_consumer) {
            //Item at index has not been produced yet:
            return null;
        }

        let index = this.current_consumer % this.capacity;
        return this.storage[index];
    }

    store(data) {
        this.current_producer++;

        let index = this.current_producer % this.capacity;
        this.storage[index] = data;
    }


}