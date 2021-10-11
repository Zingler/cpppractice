#include <iostream>

using namespace std;

// Debugger challenge! Code contains a couple of errors that produce unexpected results.

template <typename T>
void bubbleSort(T list[], size_t size, bool ascending) {
    while (true) {
        bool changed;
        for (int i = 0; i < size; i++) {
            bool shouldSwap = list[i] > list[i+1] && ascending || list[i] < list[i+1] && !ascending;
            if (shouldSwap) {
                swap(list[i], list[i + 1]);
                changed = true;
            }
        }
        if (!changed) {
            return;
        }
    }
}

void testOne() {
    char chars[] = {'e', 'd', 'c', 'b', 'a'};
    bubbleSort(chars, sizeof(chars), false);
    cout << chars[0] << chars[1] << chars[2] << chars[3] << chars[4] << endl;
}

void testTwo() {
    char chars[] = {'e', 'c', 'd', 'b', 'a'};
    bubbleSort(chars, sizeof(chars), false);
    cout << chars[0] << chars[1] << chars[2] << chars[3] << chars[4] << endl;
}

void testThree() {
    char chars[] = {'a', 'c', 'b', 'd', 'e'};
    bubbleSort(chars, sizeof(chars), true);
    cout << chars[0] << chars[1] << chars[2] << chars[3] << chars[4] << endl;
}

void testFour() {
    int ints[] = {1, 3, 2, 4, 5};
    bubbleSort(ints, sizeof(ints), true);
    cout << ints[0] << ints[1] << ints[2] << ints[3] << ints[4] << endl;
}

int main() {
    testOne(); 

    // TODO: figure out why these tests don't work?
    //testTwo();
    //testThree();
    //testFour();
}