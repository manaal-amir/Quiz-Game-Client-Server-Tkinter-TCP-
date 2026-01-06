# QuiznGame TCP Quiz — Client/Server (Tkinter + TCP)

This repository contains a simple **TCP-based quiz game** with:
- `server.py`: TCP quiz server (authoritative game state + scoring)
- `client.py`: Tkinter GUI client (connects, sends username + answers, displays questions/scoreboard)

The design explicitly handles **TCP stream behavior** (messages can arrive split/combined) and **Tkinter thread-safety** (GUI updates must run on the main thread).

---

## Files

- **`client.py`**
  - Tkinter GUI
  - Connect/disconnect controls (server/port/username)
  - Receives and displays:
    - `QUESTION ...` blocks (with `A)`, `B)`, `C)`)
    - `CURRENT SCOREBOARD:`
    - `FINAL SCOREBOARD:`
    - `FINAL RANKINGS:`
  - Sends:
    - username on connect
    - `A` / `B` / `C` when submitting an answer

- **`server.py`**
  - TCP server that accepts clients
  - Sends questions, validates answers, computes scores/bonus (server-side), broadcasts scoreboard

> Note: Scoring/bonus logic is **server-side** by design. The client only displays received scores.

---

## Requirements

- Python 3.8+
- Standard library only:
  - `tkinter`, `socket`, `threading`, `re`

---

## How to Run

### 1) Start the server

server.py  

### 2) Start the client (in another terminal)  

client.py  

### 3) Connect from the GUI  
In the client window:  

Server: 127.0.0.1 (or your server IP)  
Port: whatever server.py is configured to use  
Username: any name  
Click Connect   

When a question appears:  

Choose A/B/C  
Click Submit Answer  

 
On connect, the client sends the username immediately:   
clientSock.sendall(username.encode())  

On submit, the client sends the selected option:
clientSock.sendall(ans.encode())   # ans is "A", "B", or "C"  


  
