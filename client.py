import tkinter as tk
import socket
import threading
import re

clientSock = None
gameStage = "disconnected"

#retain final results after server disconnects
lastFinalBoardText = ""

#main window
root = tk.Tk()
root.title("SUquid Game Client")

#color codes
bgColor = "#1e1e1e"
frameColor = "#2b2b2b"
fgColor = "white"
accentColor = "#ff1493"
btnColor = "#000000"

root.configure(bg=bgColor)

def ui_call(fn, *args, **kwargs):
    root.after(0, lambda: fn(*args, **kwargs))

#Logging utility
def logMsg(msg):
    logBox.config(state="normal")
    logBox.insert(tk.END, msg + "\n")
    logBox.config(state="disabled")
    logBox.see(tk.END)

#GUI update helpers
def updateBoard(text):
    global lastFinalBoardText

    t = (text or "").strip()
    if t.startswith("FINAL SCOREBOARD:") or t.startswith("FINAL RANKINGS:"):
        lastFinalBoardText = t

    boardBox.config(state="normal")
    boardBox.delete("1.0", tk.END)
    boardBox.insert(tk.END, text)
    boardBox.config(state="disabled")

def setAnswerControls(enabled: bool):
    state = "normal" if enabled else "disabled"
    radioA.config(state=state)
    radioB.config(state=state)
    radioC.config(state=state)
    submitBtn.config(state=state)
    
    
    
    
    
    
#-------------------------------------------   







#Connection logic
def connectServer():
    global clientSock, gameStage, recv_buffer, lastFinalBoardText, seen_notify
    host = serverEntry.get().strip()
    portText = portEntry.get().strip()
    username = nameEntry.get().strip()

    if not host or not portText or not username:
        ui_call(logMsg, "ERROR: Server, Port, and Username cannot be empty")
        return
    if not portText.isdigit():
        ui_call(logMsg, "ERROR: Port must be numeric")
        return

    port = int(portText)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        clientSock = s
        gameStage = "connected"

        recv_buffer = ""
        lastFinalBoardText = ""  #clear previous run final board
        seen_notify = set()      #reset join/disconnect dedupe

        ui_call(connectBtn.config, state="disabled")
        ui_call(disconnectBtn.config, state="normal")

        #making sure enable submit/radios until a question arrives
        ui_call(setAnswerControls, False)
        ui_call(ansVar.set, "")

        ui_call(questionLbl.config, text="Waiting for question...", fg=accentColor)
        ui_call(updateBoard, "")

        ui_call(logMsg, "INFO: Connected to server")
        clientSock.sendall(username.encode())

        threading.Thread(target=checkData, daemon=True).start()
    except Exception as e:
        ui_call(logMsg, f"ERROR: Connection failed ({e})")

def disconnectServer():
    global clientSock, gameStage

    if gameStage == "disconnected":
        return

    try:
        if clientSock:
            clientSock.close()
    except Exception as e:
        ui_call(logMsg, f"ERROR: Problem closing socket ({e})")

    gameStage = "disconnected"
    ui_call(connectBtn.config, state="normal")
    ui_call(disconnectBtn.config, state="disabled")

    ui_call(setAnswerControls, False)
    ui_call(ansVar.set, "")

    ui_call(questionLbl.config, text="Waiting for question...", fg=accentColor)

    #Keep final results visible if we have them
    if lastFinalBoardText:
        ui_call(updateBoard, lastFinalBoardText)
    else:
        ui_call(updateBoard, "")

    ui_call(logMsg, "INFO: Disconnected from server")

def sendAnswer():
    global clientSock
    ans = ansVar.get()
    if ans:
        try:
            clientSock.sendall(ans.encode())
            ui_call(logMsg, f"SENT: {ans}")

            #lock after submitting
            ui_call(setAnswerControls, False)
        except Exception as e:
            ui_call(logMsg, f"ERROR: Failed to send answer ({e})")
    else:
        ui_call(logMsg, "ERROR: No answer selected")
        
               
               
               
#-------------------------------------------
        
        
        
        

#parsing for TCP stream
recv_buffer = ""

#score line in server
SCORE_LINE_RE = re.compile(r"^.+:\s*\d+\s*$")

#JOIN message 
JOIN_LINE_RE = re.compile(r"'[^']+'\s+has\s+joined\s+the\s+server\.", re.IGNORECASE)

#DISCONNECT message 
DISC_LINE_RE = re.compile(r"^[^\n]*\bhas\s+disconnected\b[^\n]*\.", re.IGNORECASE | re.MULTILINE)

seen_notify = set()

def emit_notifications_from_text(text: str):
    #Joined
    for m in JOIN_LINE_RE.finditer(text):
        msg = m.group(0).strip()
        if msg and msg not in seen_notify:
            seen_notify.add(msg)
            ui_call(logMsg, "RECV: " + msg)

    #Disconnected 
    for m in DISC_LINE_RE.finditer(text):
        msg = m.group(0).strip()
        if msg and msg not in seen_notify:
            seen_notify.add(msg)
            ui_call(logMsg, "RECV: " + msg)

def _find_question_block(buf: str):
    """
    Match only real question headers at start-of-line:
      QUESTION 3:
    Not: RESULTS FOR QUESTION 3:
    """
    #look for "\nQUESTION " or "QUESTION " at buffer start
    start = buf.find("\nQUESTION ")
    if start == -1:
        if buf.startswith("QUESTION "):
            start = 0
        else:
            return None
    else:
        start += 1  #skip the '\n'

    sub = buf[start:]

    if ("A)" not in sub) or ("B)" not in sub) or ("C)" not in sub):
        return None

    #End after the newline following the C) line
    cpos = sub.find("C)")
    after_c = sub.find("\n", cpos)
    if after_c == -1:
        return None  #wait for the rest to arrive

    end = start + after_c + 1
    block = buf[start:end].strip()
    return (block, start, end)


def _find_scoreboard_block(buf: str, header: str):
    """
    Complete scoreboard = header exists + at least one 'name: number' line after it.
    End = after the last contiguous score line.
    """
    start = buf.find(header)
    if start == -1:
        return None

    sub = buf[start:]
    lines = sub.splitlines()
    if len(lines) < 2:
        return None

    score_lines = []
    for ln in lines[1:]:
        if SCORE_LINE_RE.match(ln.strip()):
            score_lines.append(ln)
        else:
            break

    if not score_lines:
        return None

    #End after header line + score_lines
    count_lines = 1 + len(score_lines)
    pos = 0
    seen = 0
    while pos < len(sub) and seen < count_lines:
        nl = sub.find("\n", pos)
        if nl == -1:
            pos = len(sub)
            break
        pos = nl + 1
        seen += 1

    end = start + pos
    block = buf[start:end].strip()
    return (block, start, end)

def _consume_and_display():
    """
    Consume complete blocks from recv_buffer and update UI.
    """
    global recv_buffer

    changed = True
    while changed:
        changed = False

        #QUESTION blocks
        q = _find_question_block(recv_buffer)
        if q:
            block, s, e = q
            ui_call(questionLbl.config, text=block, fg=accentColor)
            ui_call(ansVar.set, "")
            ui_call(setAnswerControls, True)
            recv_buffer = recv_buffer[:s] + recv_buffer[e:]
            changed = True
            continue

        #CURRENT SCOREBOARD
        cs = _find_scoreboard_block(recv_buffer, "CURRENT SCOREBOARD:")
        if cs:
            block, s, e = cs
            ui_call(updateBoard, block)
            recv_buffer = recv_buffer[:s] + recv_buffer[e:]
            changed = True
            continue

        #FINAL SCOREBOARD
        fs = _find_scoreboard_block(recv_buffer, "FINAL SCOREBOARD:")
        if fs:
            block, s, e = fs
            ui_call(updateBoard, block)
            recv_buffer = recv_buffer[:s] + recv_buffer[e:]
            changed = True
            continue

        #FINAL RANKINGS (bounded if Game finished exists; otherwise shows partial)
        fr_start = recv_buffer.find("FINAL RANKINGS:")
        if fr_start != -1:
            gf = recv_buffer.find("Game finished.", fr_start)
            if gf != -1:
                block = recv_buffer[fr_start:gf].strip()
                ui_call(updateBoard, block)
                recv_buffer = recv_buffer[:fr_start] + recv_buffer[gf:]
                changed = True
                continue
            else:
                block = recv_buffer[fr_start:].strip()
                ui_call(updateBoard, block)
                break

def checkData():
    global clientSock, gameStage, recv_buffer

    while gameStage != "disconnected":
        try:
            data = clientSock.recv(4096)

            if not data:
                ui_call(logMsg, "INFO: Server closed the connection.")
                ui_call(disconnectServer)
                break

            chunk = data.decode(errors="replace")

            #log join/disconnect immediately (does NOT affect leaderboard/question parsing)
            emit_notifications_from_text(chunk)

            recv_buffer += chunk

            #If server rejects because game already started
            if "Game already started. Connection rejected." in recv_buffer:
                ui_call(logMsg, "ERROR: Game already started. Connection rejected.")
                ui_call(disconnectServer)
                break

            #Disable answers on finish
            if "Game finished." in recv_buffer:
                ui_call(logMsg, "INFO: Game finished.")
                ui_call(setAnswerControls, False)

            #consume structured blocks
            _consume_and_display()

            #log non-block lines 
            while True:
                nl = recv_buffer.find("\n")
                if nl == -1:
                    break

                line = recv_buffer[:nl].strip()
                if not line:
                    recv_buffer = recv_buffer[nl + 1:]
                    continue

                #don't flush if a major block begins here (wait for parser)
                if (line.startswith("QUESTION") or
                    line.startswith("CURRENT SCOREBOARD:") or
                    line.startswith("FINAL SCOREBOARD:") or
                    line.startswith("FINAL RANKINGS:")):
                    break

                #Avoid duplicating join/disconnect lines 
                if JOIN_LINE_RE.fullmatch(line) or ("has disconnected" in line.lower()):
                    recv_buffer = recv_buffer[nl + 1:]
                    continue

                ui_call(logMsg, "RECV: " + line)
                recv_buffer = recv_buffer[nl + 1:]

        except Exception as e:
            ui_call(logMsg, f"ERROR: Connection lost ({e})")
            ui_call(disconnectServer)
            break





#-------------------------------------------






#GUI Layout

#Middle: Question
questionFrame = tk.LabelFrame(root, text="Question", fg=accentColor, bg=frameColor)
questionFrame.pack(fill="x", padx=5, pady=5)

questionLbl = tk.Label(questionFrame, text="Waiting for question...",
                       wraplength=500, justify="center",
                       fg=accentColor, bg=frameColor)
questionLbl.pack(anchor="center")

#Center: Options
optionsFrame = tk.Frame(root, bg=bgColor)
optionsFrame.pack(fill="x", padx=5, pady=10)

ansVar = tk.StringVar(value="")

#start disabled radio buttons
radioA = tk.Radiobutton(optionsFrame, text="A", variable=ansVar, value="A",
                        fg=accentColor, bg=bgColor, selectcolor="black", state="disabled")
radioB = tk.Radiobutton(optionsFrame, text="B", variable=ansVar, value="B",
                        fg=accentColor, bg=bgColor, selectcolor="black", state="disabled")
radioC = tk.Radiobutton(optionsFrame, text="C", variable=ansVar, value="C",
                        fg=accentColor, bg=bgColor, selectcolor="black", state="disabled")

radioA.pack(anchor="center", pady=2)
radioB.pack(anchor="center", pady=2)
radioC.pack(anchor="center", pady=2)

submitBtn = tk.Button(optionsFrame, text="Submit Answer", command=sendAnswer,
                      state="disabled", fg=accentColor, bg=btnColor)
submitBtn.pack(pady=10)

#Left: Leaderboard
boardFrame = tk.LabelFrame(root, text="Leaderboard", fg=accentColor, bg=frameColor)
boardFrame.pack(side="left", fill="y", padx=5, pady=5)

boardBox = tk.Text(boardFrame, width=30, height=20, state="disabled",
                   fg=fgColor, bg=frameColor)
boardBox.pack(fill="y")

#Right: Activity Log
logFrame = tk.LabelFrame(root, text="Activity Log", fg=accentColor, bg=frameColor)
logFrame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

logBox = tk.Text(logFrame, width=50, height=20, state="disabled",
                 fg=fgColor, bg=frameColor)
logBox.pack(fill="both", expand=True)

#Bottom: Connection Controls
connFrame = tk.Frame(root, bg=bgColor)
connFrame.pack(side="bottom", fill="x", padx=5, pady=5)

serverLbl = tk.Label(connFrame, text="Server:", fg=accentColor, bg=bgColor)
serverLbl.grid(row=0, column=0, sticky="w")
serverEntry = tk.Entry(connFrame, fg=fgColor, bg=frameColor, insertbackground=fgColor)
serverEntry.grid(row=0, column=1, sticky="we")

portLbl = tk.Label(connFrame, text="Port:", fg=accentColor, bg=bgColor)
portLbl.grid(row=1, column=0, sticky="w")
portEntry = tk.Entry(connFrame, fg=fgColor, bg=frameColor, insertbackground=fgColor)
portEntry.grid(row=1, column=1, sticky="we")

nameLbl = tk.Label(connFrame, text="Username:", fg=accentColor, bg=bgColor)
nameLbl.grid(row=2, column=0, sticky="w")
nameEntry = tk.Entry(connFrame, fg=fgColor, bg=frameColor, insertbackground=fgColor)
nameEntry.grid(row=2, column=1, sticky="we")

connectBtn = tk.Button(connFrame, text="Connect", command=connectServer,
                       fg=accentColor, bg=btnColor)
connectBtn.grid(row=0, column=2, padx=5)

disconnectBtn = tk.Button(connFrame, text="Disconnect", command=disconnectServer,
                          state="disabled", fg=accentColor, bg=btnColor)
disconnectBtn.grid(row=1, column=2, padx=5)

connFrame.grid_columnconfigure(1, weight=1)

#run main loop
root.mainloop()
