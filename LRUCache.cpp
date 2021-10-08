#include <array>
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
#include <cassert>

using namespace std;

template <class K, class V>
struct Node {
    std::optional<K> key = nullopt;
    V value;
    Node* prev;
    Node* next;
};

template <class K, class V>
class LRUCache {
   public:
    LRUCache(int size) : list(size) {
        Node<K,V>* prev = nullptr;
        for (int i = 0; i < size; i++) {
            list[i].prev = prev;
            if (prev != nullptr) {
                prev->next = &list[i];
            }
            prev = &list[i];
        }
        mostRecent = &list[0];
        leastRecent = &list[size - 1];
    }

    void put(K key, V value) {
        Node<K,V>* node;
        if (hash.find(key) == hash.end()) {
            if (leastRecent->key) {
                hash.erase(leastRecent->key.value());
            }
            node = leastRecent;
            node->key = key;
            hash[key] = node;
        } else {
            node = hash[key];
        }
        node->value = value;

        removeNode(node);
        placeAsMostRecent(node);
    }

    optional<V> get(K key) {
        if (hash.find(key) != hash.end()) {
            auto node = hash[key];
            removeNode(node);
            placeAsMostRecent(node);
            return make_optional(hash[key]->value);
        }
        return nullopt;
    }

   private:
    vector<Node<K,V>> list;
    unordered_map<K, Node<K,V>*> hash;
    Node<K,V>* mostRecent;
    Node<K,V>* leastRecent;

    void removeNode(Node<K,V>* node) {
        auto prev = node->prev;
        if (prev != nullptr) {
            prev->next = node->next;
        }
        if (node->next != nullptr) {
            node->next = prev;
        } else {
            leastRecent = prev;
        }
    }
    void placeAsMostRecent(Node<K,V>* node) {
        node->prev = nullptr;
        node->next = mostRecent;
        mostRecent->prev = node;
        mostRecent = node;
    }
};

int main() {
    LRUCache<string, int> cache(3);
    cache.put("one", 1);
    cache.put("two", 2);
    cache.put("three", 3);

    cache.get("one");

    cache.put("four", 4);

    assert(cache.get("one") != nullopt);
    assert(cache.get("two") == nullopt);
    assert(cache.get("three") != nullopt);
    assert(cache.get("four") != nullopt);
    cout << "success" << endl;
}