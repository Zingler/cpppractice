#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <optional>
#include <queue>
#include <thread>

using namespace std;

template <class T>
class BlockingQueue {
    queue<T> _queue;
    int _maxSize;
    mutex lock;
    condition_variable can_produce; 
    condition_variable can_consume;
    atomic<bool> _shutdown = false; // Unsure if this needs to be atomic

   public:
    BlockingQueue(int maxSize) : _maxSize(maxSize) {}

    // Blocks until the item can be added. Throws exception if pool was shutdown before this call to add.
    void add(T item) {
        unique_lock<mutex> l(lock);
        if (_shutdown) {
            throw -1;
        }
        while (_queue.size() >= _maxSize) {
            can_produce.wait(l);
        }
        _queue.push(item);
        can_consume.notify_one();
    }

    // Blocks until a value is available. Returns nullopt when queue is shutdown
    // and no elements remaining.
    optional<T> poll() {
        unique_lock<mutex> l(lock);
        while (_queue.size() == 0) {
            if (_shutdown) {
                return nullopt;
            }
            can_consume.wait(l); 
        }
        T value = _queue.front();
        _queue.pop();
        can_produce.notify_one();
        return value;
    }

    void shutdown() {
        unique_lock<mutex> l(lock);
        _shutdown = true;
        can_consume.notify_all(); // Wake all consumers so they recognize to drain the queue.
    }
};

void producer(BlockingQueue<int>& queue) {
    for (int i = 0; i <= 100; i++) {
        this_thread::sleep_for(chrono::milliseconds(1)); // simulate some producing delay
        queue.add(i);
    }
}

mutex logger;

void consumer(BlockingQueue<int>& queue, atomic<int>& sum) {
    int localSum = 0;
    while (auto value = queue.poll()) { // returns nullopt if queue is shutdown and no elements are remaining.
        this_thread::sleep_for(chrono::milliseconds(1)); // simulate some consuming delay
        localSum += value.value();
    }
    lock_guard l(logger);
    cout << "Local consumer sum: " << localSum << endl;
    sum += localSum;
}

int main() {
    BlockingQueue<int> queue(10);
    atomic<int> sum = 0;
    const int PRODUCERS = 100;
    const int CONSUMERS = 100;

    vector<thread> producers;
    for(int i=0; i<PRODUCERS; i++) {
        producers.push_back(thread([&]{
            producer(queue);
        }));
    }
    vector<thread> consumers;
    for(int i=0; i<CONSUMERS; i++) {
        consumers.push_back(thread([&]{
            consumer(queue, sum);
        }));
    }

    for(auto &t: producers) {
        t.join();
    }
    
    queue.shutdown();

    for(auto &t: consumers) {
        t.join();
    }

    cout << "Total sum: " << sum << endl;
}