import requests

try:
    response = requests.post('http://localhost:5000/requestVote', json={'term':13,'candidate':'biden'})
    print(response)
    print(response.json())
except Exception as e:
    print("exception")