from typing import ValuesView
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

#http.client.HTTPConnection.debuglevel = 1

#logging.basicConfig()
#logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
#requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True

retry_strategy = Retry(total=1)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("http://", adapter)

servers = ['server1', 'server2', 'server3']
# servers = ['server1']
me = os.getenv('NAME') or 'server1'

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
            self.updateEvent()
        self.state = State.FOLLOWER
    def becomeLeader(self, term):
        self.leader_term = self.term
        self.state = State.LEADER
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
        self.unlock()
        start = datetime.now()
        for server in servers:
            if(server == me):
                continue
            try:
                response = http.post(f'http://{server}:5000/appendEntries', json={'term':leader_term,'leader':me}, timeout=1)
                r_term = response['term']
                if(response['term'] > leader_term):
                    with cstate:
                        cstate.becomeFollower(r_term)
                    return
            except Exception as e:
                pass
        wait_time = (term_timeout/4) - (datetime.now() - start).seconds 
        if(wait_time > 0):
            time.sleep(wait_time)

    def candidate(self):
        self.term += 1
        candidate_term = self.term
        print(f'Starting election for myself term {candidate_term}')
        self.updateEvent()
        self.vote = me 
        vote_count = 1
        random.shuffle(servers)
        self.unlock()

        for server in servers:
            if(server == me):
                continue
            response = collectVote(server,candidate_term)
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
        if(cstate.state == State.FOLLOWER):
            cstate.follower()
        elif(cstate.state == State.CANDIDATE):
            cstate.candidate()
        elif(cstate.state == State.LEADER):
            cstate.leader(cstate.leader_term)


def collectVote(server, term):
    try:
        response = http.post(f'http://{server}:5000/requestVote', json={'term':term,'candidate':me}, timeout=1)
        return response.json()
    except Exception as e:
        print(f"Exception getting vote from {server}")
        return {'grant':False, 'term':term}

@app.route('/requestVote', methods=["POST"])
def requestVote():
    data = request.get_json(force=True)
    request_term = data['term']
    request_candidate = data['candidate']

    print(f"Recieved request vote from {request_candidate} for term {request_term}")

    with cstate:
        if(request_term > cstate.term):
            print(f'Recieved ballot for later term. Becoming a follower.')
            cstate.becomeFollower(request_term)

        grant = False
        if cstate.term == request_term and (cstate.vote == None or cstate.vote == request_candidate):
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
    request_candidate = data['leader']

    success = False
    with cstate:
        if(request_term > cstate.term):
            cstate.becomeFollower(request_term)

        if(request_term == cstate.term):
            cstate.becomeFollower(request_term)
            cstate.updateEvent()
            success = True
        return {'success': success, 'term': cstate.term}


if __name__ == '__main__':
    threading.Thread(target=machine).start()
    app.run(host='0.0.0.0')
