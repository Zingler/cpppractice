from typing import ValuesView
from typing import List
from flask import Flask
from flask import request
from enum import Enum
import threading
from datetime import datetime
import time
import requests
import os
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import http
import logging
from collections import namedtuple

LogEntry = namedtuple('LogEntry', ['term', 'log'])

retry_strategy = Retry(total=1)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("http://", adapter)

servers = ['10.0.0.3', '10.0.0.4', '10.0.0.5']
# servers = ['server1']
me = os.getenv('NAME') or '10.0.0.3'
print(f'My name is {me}')

term_timeout = 20

app = Flask(__name__)


class State(Enum):
    LEADER = 1
    FOLLOWER = 2
    CANDIDATE = 3


class CState:
    def __init__(self):
        self.state = State.FOLLOWER
        self.term = 0
        self.mutex = threading.RLock()
        self.last_event = datetime.now()
        self.vote = None
        self.log = [LogEntry(-10, "Initialize")]
        self.commit_index = 0
        self.last_applied = 1
        self.leaderId = None

    def __enter__(self):
        self.mutex.acquire()

    def __exit__(self, type, value, trace):
        self.mutex.release()
    
    def lock(self):
        self.mutex.acquire()
    def unlock(self):
        self.mutex.release()
    
    def becomeFollower(self, term):
        if(term > self.term):
            self.term = term
            self.vote = None
        self.state = State.FOLLOWER
    def becomeLeader(self, term):
        self.leader_term = self.term
        self.state = State.LEADER
        self.nextIndex = {x: len(self.log) for x in servers}
        self.matchIndex = {x: 0 for x in servers}
    def becomeCandidate(self):
        self.state = State.CANDIDATE
    
    def updateEvent(self):
        self.last_event = datetime.now()

    def follower(self):
        last_event = self.last_event
        if (datetime.now() - last_event).seconds > term_timeout:
            self.becomeCandidate()
            self.unlock()
            return
        self.unlock()
        time.sleep(3)
    
    def leader(self, leader_term):
        print(f'Sending leader hearbeats for term {leader_term}')
        start = datetime.now()

        for server in servers:
            if(server == me):
                continue
            self.sendUpdates(server, leader_term)
        self.updateCommitIndex()
        self.unlock()

        wait_time = (term_timeout/4) - (datetime.now() - start).seconds 
        if(wait_time > 0):
            time.sleep(wait_time)

    def sendUpdates(self, server, leader_term):
        data = {
            'term': self.leader_term,
            'leader':me,
            'entries': [x._asdict() for x in self.log[self.nextIndex[server]:]],
            'prevLogIndex': self.nextIndex[server]-1,
            'prevLogTerm': self.log[self.nextIndex[server]-1].term,
            'leaderCommit': self.commit_index,
            }
        try:
            response = http.post(f'http://{server}:5000/appendEntries', json=data, timeout=1).json()
            if(response['success']):
                self.nextIndex[server] = len(self.log)
                self.matchIndex[server] = len(self.log)
            else:
                self.nextIndex[server] -= 1
                print(f"Failed to update log for {server}. Decremented nextIndex to {self.nextIndex[server]}.")

            r_term = response['term']
            if(response['term'] > leader_term):
                self.becomeFollower(r_term)
        except Exception as e:
            print(f"Failed to connect to {server} to append entries. Continuing on.", e)

    def updateCommitIndex(self):
        new_commit = len(self.log)-1
        threshold = (len(servers) // 2) + 1
        while new_commit > self.commit_index:
            if self.log[new_commit].term == self.term and \
                sum((self.matchIndex[s] >= new_commit for s in servers)) >= threshold:
                self.commit_index = new_commit
                print(f"Updating leader commit index to {self.commit_index} log line {self.log[self.commit_index].log}")
                return

            new_commit -= 1

    def candidate(self):
        self.term += 1
        candidate_term = self.term
        print(f'Starting election for myself term {candidate_term}')
        self.updateEvent()
        self.vote = me 
        vote_count = 1
        last_log_index = len(self.log)-1
        last_log_term = self.log[last_log_index].term
        random.shuffle(servers)
        self.unlock()

        for server in servers:
            if(server == me):
                continue
            response = collectVote(server,candidate_term, last_log_index, last_log_term)
            r_term = response['term']
            with cstate:
                if(r_term > self.term):
                    self.becomeFollower(r_term)
                    return
            if(response['grant']):
                vote_count+=1
            if vote_count * 2 > len(servers):
                break
        with cstate:
            if vote_count * 2 > len(servers) and self.state == State.CANDIDATE and candidate_term == self.term:
                print(f'Got enough votes for term {candidate_term}. Becoming leader.')
                self.becomeLeader(candidate_term)
                return
        time.sleep(5)

cstate = CState()

def machine():
    while True:
        cstate.lock()
        print(f"Commited : {cstate.commit_index}. Log length: {len(cstate.log)}. Term {cstate.term}.")
        if(cstate.state == State.FOLLOWER):
            cstate.follower()
        elif(cstate.state == State.CANDIDATE):
            cstate.candidate()
        elif(cstate.state == State.LEADER):
            cstate.leader(cstate.leader_term)


def collectVote(server, term, last_log_index, last_log_term):
    try:
        data = {
            'term':term,
            'candidate':me,
            'lastLogIndex':last_log_index,
            'lastLogTerm':last_log_term,
        }
        response = http.post(f'http://{server}:5000/requestVote', json=data, timeout=1)
        return response.json()
    except Exception as e:
        print(f"Exception getting vote from {server}")
        return {'grant':False, 'term':term}

@app.route('/requestVote', methods=["POST"])
def requestVote():
    data = request.get_json(force=True)
    request_term = data['term']
    request_candidate = data['candidate']
    last_log_index = data['lastLogIndex']
    last_log_term = data['lastLogTerm']

    print(f"Recieved request vote from {request_candidate} for term {request_term}")

    with cstate:
        if(request_term > cstate.term):
            print(f'Recieved ballot for later term. Becoming a follower.')
            cstate.becomeFollower(request_term)

        grant = False

        larger_term = last_log_term > cstate.log[-1].term 
        equal_term = last_log_term == cstate.log[-1].term 
        longer_log = last_log_index >= len(cstate.log)-1
        log_is_newer = larger_term or (equal_term and longer_log)

        if cstate.term == request_term \
            and (cstate.vote == None or cstate.vote == request_candidate) \
            and log_is_newer: 
            cstate.vote = request_candidate
            cstate.updateEvent()
            grant = True

        print(f'Voting for {request_candidate} for term {request_term} : Grant = {grant}')
        response = {'grant': grant, 'term': cstate.term}

    return response


@app.route('/appendEntries', methods=["POST"])
def appendEntries():
    data = request.get_json(force=True)
    request_term = data['term']
    leader = data['leader']
    prevLogIndex = data['prevLogIndex']
    prevLogTerm = data['prevLogTerm']
    entries = [LogEntry(**x) for x in data['entries']]
    leaderCommit = data['leaderCommit']

    success = False
    with cstate:
        if(request_term > cstate.term):
            cstate.becomeFollower(request_term)
            cstate.updateEvent()

        if(request_term < cstate.term):
            return {'success':False, 'term': cstate.term}
        if(request_term == cstate.term):
            cstate.becomeFollower(request_term)
            cstate.updateEvent()
            cstate.leaderId = leader
            success = True
        if(prevLogIndex >= len(cstate.log) or cstate.log[prevLogIndex].term != prevLogTerm):
            cstate.updateEvent()
            return {'success':False, 'term': cstate.term}
        
        updateLogs(cstate.log, prevLogIndex, entries)

        if(leaderCommit > cstate.commit_index):
            cstate.commit_index = min(leaderCommit, len(cstate.log)-1)
            print(f"Updating follower commit index to {cstate.commit_index} log line {cstate.log[cstate.commit_index].log}")

        return {'success': success, 'term': cstate.term}

def updateLogs(log: List[LogEntry], prevLogIndex, entries):
    i = prevLogIndex
    for e in entries:
        i+=1
        if i<len(log):
            if log[i].term != e.term:
                del log[i:]
                log.append(e)
        else:
            log.append(e)


@app.route('/submit', methods=["POST"])
def submit():
    data = request.get_json(force=True)
    log = data['log']
    with cstate:
        if cstate.state != State.LEADER:
            if cstate.leaderId:
                http.post(f"http://{cstate.leaderId}:5000/submit", json=data, timeout=1)
                return {'success':True}
            else:
                return {'success':False}
        
        cstate.log.append(LogEntry(cstate.term,log))
        cstate.matchIndex[me] = len(log)-1
        print(f'Added log entry as leader {cstate.log[-1]}')
    return {'success': True}
        

if __name__ == '__main__':
    threading.Thread(target=machine).start()
    app.run(host='0.0.0.0')
