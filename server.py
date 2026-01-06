import tkinter as tk
from tkinter import messagebox
import socket
import threading
import time

#colors for the GUI
BG_MAIN = "#166B61"       
BG_FRAME = "#166B61"       
BTN_BG = "#11574F"        
BTN_FG = "#FFFFFF"        
LABEL_FG = "#FCFCFC"       
LISTBOX_BG = "#B7E6DF"     

class GameServer:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.configure(bg=BG_MAIN)
        master.title("Project Game Server")

        self.master.grid_columnconfigure(0, weight=1)

        self.master.grid_rowconfigure(5, weight=1)
        self.master.grid_rowconfigure(7, weight=2)

        self.server_socket = None
        self.is_listening = False
        self.is_resetting = False
        self.thread = None

        self.clients_dict = {} #{ name: {sock, addr, connected, disconnected_during_game} }

        self.scoreboard = {} #scoreboard: {name: int} initialised

        self.questions = [] #nested list, each question, its options and correct answer are one list inside this list
        self.num_of_questions = 0

        self.answer_lock = threading.Lock()

        self.state = "WAITING" #inital state is waiting

        self.create_widgets()

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing) #check

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------
#Socket GUI
    def create_widgets(self):

       #PORT
        port_frame = tk.Frame(self.master, bg=BG_FRAME)
        port_frame.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        port_frame.grid_columnconfigure(index=[0,1] , weight=1)
        port_frame.grid_rowconfigure(index=0, weight=1)

        tk.Label(port_frame, text="Port:", bg=BG_FRAME, fg=LABEL_FG).grid(row=0, column=0, sticky="w")
        self.port_entry = tk.Entry(port_frame, width=15, bg=LISTBOX_BG, fg="#000000")
        self.port_entry.grid(row=0, column=1, sticky="w", padx=5)

        self.listen_button = tk.Button(port_frame, text="Start Listening", command=self.toggle_listening, bg=BTN_BG, fg=BTN_FG, activebackground="#80CBC4")
        self.listen_button.grid(row=0, column=2, sticky="w", padx=10)

        #---------------------------------------------------------------------------------------------------
        #Question File

        question_frame = tk.Frame(self.master, bg=BG_FRAME)
        question_frame.grid(row=1, column=0, sticky="w", padx=10, pady=5)

        tk.Label(question_frame, text="TXT Question File:", bg=BG_FRAME, fg=LABEL_FG).grid(row=0, column=0, sticky="w")
        self.question_entry = tk.Entry(question_frame, width=40, bg=LISTBOX_BG, fg="#000000")
        self.question_entry.grid(row=0, column=1, sticky="w", padx=5)

        self.load_button = tk.Button(question_frame, text="Load Questions", command=self.load_questions, bg=BTN_BG, fg=BTN_FG, activebackground="#80CBC4")
        self.load_button.grid(row=0, column=2, sticky="w", padx=5)

        #---------------------------------------------------------------------------------------------------
        #Number of questions entry

        question_no_frame = tk.Frame(self.master, bg=BG_FRAME)
        question_no_frame.grid(row=2, column=0, sticky="w", padx=10, pady=5)

        tk.Label(question_no_frame, text="Total Questions", bg=BG_FRAME, fg=LABEL_FG).grid(row=0, column=0, sticky="w")
        self.question_no_entry = tk.Entry(question_no_frame, width=20, bg=LISTBOX_BG, fg="#000000")
        self.question_no_entry.grid(row=0, column=1, sticky="w", padx=5)

        #---------------------------------------------------------------------------------------------------
        #Start/Stop Buttons

        buttons_frame = tk.Frame(self.master, bg=BG_FRAME)
        buttons_frame.grid(row=3, column=0, sticky="w", padx=10, pady=10)

        self.start_button = tk.Button(buttons_frame, text="Start Game", command=lambda: threading.Thread(target=self.start_game, daemon=True).start(), bg=BTN_BG, fg=BTN_FG, activebackground="#80CBC4")
        self.start_button.grid(row=0, column=0, sticky="w", padx=5)

        self.stop_button = tk.Button(buttons_frame, text="Stop Game (Reset)", command=self.reset_game, bg=BTN_BG, fg=BTN_FG, activebackground="#80CBC4")
        self.stop_button.grid(row=0, column=1, sticky="w", padx=5)

        #---------------------------------------------------------------------------------------------------
        #Connection display
        tk.Label(self.master, text="Connected Clients", bg=BG_FRAME, fg=LABEL_FG).grid(row=4, column=0, sticky="w", padx=10)

        self.clients_listbox = tk.Listbox(self.master, height=5, selectmode=tk.SINGLE, bg=LISTBOX_BG, fg="#000000", selectbackground="#80CBC4")
        self.clients_listbox.grid(row=5, column=0, sticky="nsew", padx=10, pady=5)

        #manual interaction is disabled
        self.clients_listbox.config(state=tk.DISABLED)
  
        #---------------------------------------------------------------------------------------------------
        #Server Log display
        tk.Label(self.master, text="Server Log", bg=BG_FRAME, fg=LABEL_FG).grid(row=6, column=0, sticky="w", padx=10)

        self.server_log_listbox = tk.Listbox(self.master, height=10, bg=LISTBOX_BG, fg="#000000", selectbackground="#80CBC4")
        self.server_log_listbox.grid(row=7, column=0, sticky="nsew", padx=10, pady=5)

        #manual interaction is disabled
        self.server_log_listbox.config(state=tk.DISABLED)


#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------

    def load_questions(self):
        path = self.question_entry.get().strip()

        if not path:
            messagebox.showerror("Error", "Please enter the question file path.")
            return
        
        list_of_lines = [] 

        try:
            #use UTF-8 encoding to avoid any errors as it is safest
            file = open(path, "r", encoding="utf-8")
            content = file.read()
            file.close()

            current_line = ""

            for ch in content:
                if ch == "\n":
                    #ignore empty lines 
                    if current_line.strip() != "":
                        list_of_lines.append(current_line.strip())
                    current_line = ""
                else:
                    current_line += ch

            if current_line.strip() != "":
                list_of_lines.append(current_line.strip())

        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")
            return

        #the file must have 5 lines per question
        if len(list_of_lines) % 5 != 0:
            messagebox.showerror(
                "Error", "question file format is incorrect.\nEach question must have exactly 5 lines.")
            return

        self.questions = []

        i = 0
        while i < len(list_of_lines):
            question = list_of_lines[i]

            #strip option prefixes 
            A = list_of_lines[i + 1].replace("A -", "").strip()
            B = list_of_lines[i + 2].replace("B -", "").strip()
            C = list_of_lines[i + 3].replace("C -", "").strip()

            answer_line = list_of_lines[i + 4]

            #extract correct answer from "Answer: X" accoridng to the txt file format
            if not answer_line.startswith("Answer:"):
                messagebox.showerror("Error", f"Invalid answer format at question starting line {i+1}.")
                self.questions = []
                return

            correct = answer_line.split(":")[1].strip().upper()

            if correct not in ("A", "B", "C"):
                messagebox.showerror("Error", f"Invalid correct answer at question starting line {i+1}.")
                self.questions = []
                return

            self.questions.append([question, A, B, C, correct])
            
            i += 5

        self.add_message_to_text(
            f"Loaded {len(self.questions)} questions successfully."
        )

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------
   
    def toggle_listening(self):
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        port_str = self.port_entry.get()
        if not port_str:
            messagebox.showerror("Error", "Please enter a port number.")
            return

        try:
            port = int(port_str)
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('0.0.0.0', port))
            self.server_socket.listen(5)
            
            self.is_listening = True
            self.listen_button.config(text="Stop Listening")
            self.add_message_to_text(f"--- Server listening on port {port} ---")
            
            self.thread = threading.Thread(target=self.accept_connections, daemon=True)
            self.thread.start()
            
            self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        except (socket.error, ValueError) as e:
            messagebox.showerror("Server Error", f"Could not start server: {e}")
            self.is_listening = False
            if self.server_socket:
                self.server_socket.close()

    def stop_listening(self):
        if self.is_listening:
            self.is_listening = False

            for conn in list(self.clients_dict.values()):
                if conn["connected"]:
                    self.remove_client(conn["sock"])

            if self.server_socket:
                self.server_socket.close()

            self.listen_button.config(text="Start Listening")
            self.add_message_to_text("--- Server stopped ---")


    def accept_connections(self):
        while self.is_listening:
            try:
                client_socket, client_address = self.server_socket.accept()

                #first check server state, only accept connections when in WAITING state
                if self.state != "WAITING":
                    client_socket.send("Game already started. Connection rejected.".encode())
                    self.add_message_to_text("Connection rejected: game already started.")
                    client_socket.close()
                    continue

                #listen for usernames
                name = client_socket.recv(1024).decode().strip()

                #if username empty, reject it
                if not name:
                    client_socket.send("Error, failed to connect. Invalid username.".encode())
                    self.add_message_to_text(f"Connection failed: user '{name}' failed to connect because the username is empty.")
                    client_socket.close()
                    continue

                #now check if the username is unique or not
                if name in self.clients_dict:
                    client_socket.send("Error: username already in use. Please choose a different username.".encode())
                    self.add_message_to_text(f"Connection failed: user '{name}' failed to connect because the username is already in use.")
                    client_socket.close()
                    continue

                #if unique username, accept client
                self.clients_dict[name] = {
                    "sock": client_socket,
                    "addr": client_address,
                    "connected": True,
                    "disconnected_during_game": False }

                #log it into the empty text space
                self.add_message_to_text(f"'{name}' has joined the server.")
                self.broadcast(f"'{name}' has joined the server.")

                #add the client to the client listbox
                self.clients_listbox.config(state=tk.NORMAL)
                self.clients_listbox.insert(tk.END, name)
                self.clients_listbox.config(state=tk.DISABLED)

                #start a thread for that client
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, name),
                    daemon=True
                )
                client_thread.start()

            except (socket.error, OSError):
                break 

    #still kept as it is a lifecycle guard thread
    def handle_client(self, client_socket, name):
        while self.is_listening:

            #if server is shutting down or in invalid state, remove client
            if self.state not in ("WAITING", "RUNNING"):
                self.remove_client(client_socket)
                break

            #during RUNNING, handle client is supposed to do nothing to avoid interfering with start_games function
            #start_game() has exclusive control over recv() in this state
            if self.state == "RUNNING":
                time.sleep(0.1)
                continue

            #WAITING state: ONLY detect disconnect, do not consume messages
            if self.state == "WAITING":
                try:
                    data = client_socket.recv(1024, socket.MSG_PEEK)

                    if not data:
                        #client disconnected
                        if not self.is_resetting:
                            self.remove_client(client_socket, f"{name} disconnected while waiting.")
                        else:
                            self.remove_client(client_socket)
                        break

                except (socket.error, OSError): 
                    if not self.is_resetting and self.state == "WAITING":
                        self.remove_client(client_socket, f"{name} disconnected while waiting.")
                    else:
                        self.remove_client(client_socket)
                    break

    def broadcast(self, ques_msg):

        for name, info in list(self.clients_dict.items()):
            if not info["connected"]:
                continue
            try:
                info["sock"].send(ques_msg.encode())
            except (socket.error, OSError):
                self.remove_client(info["sock"])

    def remove_client(self, client_socket, log_msg=None):

        #find the client by socket
        name = None
        for n, info in self.clients_dict.items():
            if info["sock"] == client_socket:
                name = n
                break
        if name is None:
            return #socket not found
        
        #already disconnected, so we need to avoid double handling
        already_disconnected = not self.clients_dict[name]["connected"]
        
        if not already_disconnected:
            try:
                client_socket.close()
            except:
                pass

        if self.state == "WAITING":
            self.clients_dict.pop(name, None)
            #update listbox for waiting state
            self.clients_listbox.config(state=tk.NORMAL)
            for i in range(self.clients_listbox.size()):
                if self.clients_listbox.get(i) == name:
                    self.clients_listbox.delete(i)
                    break
            self.clients_listbox.config(state=tk.DISABLED)

            if log_msg:
                self.add_message_to_text(log_msg)
            return

        #mark client as disconnected (but dont delete name)
        self.clients_dict[name]["connected"] = False
        self.clients_dict[name]["disconnected_during_game"] = (self.state == "RUNNING")

        #update and remove the client from the listbox
        self.clients_listbox.config(state=tk.NORMAL)
        for i in range(self.clients_listbox.size()):
            if self.clients_listbox.get(i) == name:
                self.clients_listbox.delete(i)
                break
        self.clients_listbox.config(state=tk.DISABLED)

        #to allow server log flexibility
        if log_msg:
            self.add_message_to_text(log_msg)

    def add_message_to_text(self, ques_msg):
        self.server_log_listbox.config(state=tk.NORMAL)

        #handle multi-line and single-line messages
        for line in str(ques_msg).splitlines():
            self.server_log_listbox.insert(tk.END, line)

        self.server_log_listbox.yview(tk.END)
        self.server_log_listbox.config(state=tk.DISABLED)


    def on_closing(self):
        if self.is_listening:
            self.stop_listening()
        self.master.destroy()

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------
#game logic

    def start_game_validate(self):
        #server must be listening
        if not self.is_listening:
            self.add_message_to_text("Cannot start game: server is not listening.")
            return False

        #server must be in WAITING state so that game can start
        if self.state != "WAITING":
            self.add_message_to_text("Cannot start game: server not in WAITING state.")
            return False

        #the questions must be loaded and ready to go
        if len(self.questions) == 0:
            self.add_message_to_text("Cannot start game: no questions loaded.")
            return False

        #the number of questions needs to be valid
        try:
            self.num_of_questions = int(self.question_no_entry.get().strip())

            #must be positive
            if self.num_of_questions <= 0:
                raise ValueError

        except ValueError:
            self.add_message_to_text("Cannot start game: invalid number of questions.")
            return False

        #at least 2 clients must be connected
        if len(self.curr_conn_clients()) < 2:
            self.add_message_to_text("Cannot start game: at least 2 players required.")
            return False

        #if all conditions are satisfied, then we can change the state without any issues
        return True
    
    def curr_conn_clients(self):
        return [name for name, conn in self.clients_dict.items() if conn["connected"]]
    
    def start_game(self):
        if not self.start_game_validate():
            return
        
        self.state = "RUNNING"
        self.add_message_to_text("Game started successfully.")
        self.broadcast("Game started successfully.")

        if self.state != "RUNNING":
            return

        #initialize score list (using the length of the name dictionary) (disconnected players remain here)
        self.scoreboard.clear()
        for name in self.clients_dict:
            self.scoreboard[name] = 0 #inital scores are 0 for everyone

        self.add_message_to_text("Scores initialized.")

        #now we broadcast the current scoreboard
        score_msg = "\nCURRENT SCOREBOARD:\n"
        for name, score in self.scoreboard.items():
            score_msg += name + ": " + str(score) + "\n"

        if self.state == "RUNNING":
            self.broadcast(score_msg)
            self.add_message_to_text(score_msg.strip()) #also log it on the server

        question_counter = 0 #initialise the question counter

        while question_counter < self.num_of_questions:

            if self.state != "RUNNING":
                return
            
            #we need to end the game if fewer than 2 players are there
            if len(self.curr_conn_clients()) < 2:
                self.add_message_to_text("Fewer than 2 players are on the server. Ending the game.")
                self.broadcast("Fewer than 2 players are on the server. Ending the game.")
                break

            #allow reusing questions of number of qs > questions in the file
            question = self.questions[question_counter % len(self.questions)]

            #dividing the question into its respective parts so we can broadcast only the required parts (avoid broadcasting the correct answer)
            ques_sentence = question[0]
            A = question[1]
            B = question[2]
            C = question[3]
            correct = question[4]

            #question start marker for clients
            self.broadcast(f"Question {question_counter + 1} started.")
            self.add_message_to_text(f"Question {question_counter + 1} started.")

            ques_msg = (
                "\nQUESTION " + str(question_counter + 1) + ":\n"
                + ques_sentence + "\n"
                + "A) " + A + "\n"
                + "B) " + B + "\n"
                + "C) " + C + "\n"
            )

            self.broadcast(ques_msg)
            self.add_message_to_text(ques_msg.strip())
            self.add_message_to_text("Question sent.")

            one_player_remains = False #checks if only one player remains during the question, so that the game can end after 

            #answer storage
            answers = {} #answer dictionary { name: { "answer": str, "connected": bool } }
            answer_order = [] #preserves answer arrival order

            #we need to wait for all players to answer:

            #this serves as memery holder for the amount of players right after we start the game. we update this constantly as the game runs
            expected_players = set(self.curr_conn_clients())
            while True:
                #detect players who left before answering
                current_players = set(self.curr_conn_clients())
                disconnected_players = expected_players - current_players

                if disconnected_players:
                    for left_player in disconnected_players:
                        self.add_message_to_text(f"{left_player} disconnected during the game.")
                        self.broadcast("A player has disconnected during the game.")
                        expected_players.discard(left_player)

                if not expected_players:
                    one_player_remains = True
                    break

                connected_expected = {name for name in expected_players
                                      if self.clients_dict[name]["connected"]}

                connected_answered = {name for name in answers
                                      if name in connected_expected}

                if connected_expected and len(connected_answered) >= len(connected_expected): 
                    break

                for name in list(expected_players):
                    client1 = self.clients_dict.get(name)

                    if not client1 or not client1["connected"]:
                        expected_players.discard(name)
                        continue

                    sock = client1["sock"]

                    try:
                        sock.settimeout(1.0)
                        data = sock.recv(1024).decode().strip()
                    except socket.timeout:
                        #client is still connected, just hasn't answered yet
                        continue
                    except (ConnectionResetError, OSError):
                        #actual disconnect
                        self.broadcast("A player has disconnected during the game.")
                        self.remove_client(sock, f"{name} disconnected during the game.")
                        expected_players.discard(name)

                        if len(expected_players) < 2:
                            one_player_remains = True
                        continue

                    if not data:
                        #that means a player disconnected
                        if name in answers:
                            answers[name]["connected"] = False
                        self.broadcast("A player has disconnected during the game.")
                        self.remove_client(sock, f"{name} disconnected during the question.")
                        expected_players.discard(name)

                        if len(expected_players) < 2:
                            one_player_remains = True
                        continue

                    answer = data.upper() #uppercasing possible lower answers to match format just incase

                    #checking answer inputs just incase as well
                    with self.answer_lock:
                        if name in answers:
                            sock.send("You already answered this question.".encode())
                            continue

                        if answer not in ("A", "B", "C"):
                           sock.send("Invalid answer. Please send A, B, or C.".encode())
                           continue

                        answers[name] = {"answer": answer, "connected": True} 
                        answer_order.append(name)

                        sock.send("Answer received.".encode())
                        self.add_message_to_text(f"{name} answered: {answer}")
                
                time.sleep(0.05)

            #question end marker for clients
            self.broadcast(f"Question {question_counter + 1} ended.")

            #rechecking the total number of players when points are being finalised, to check whos active and who disconnected
            active_players = [name for name, data in answers.items()
                              if data["connected"] and self.clients_dict[name]["connected"]]

            #we calculate results only after all answers are collected 
            first_correct = None
            for name in answer_order:
                if (answers[name]["answer"] == correct and answers[name]["connected"] and self.clients_dict[name]["connected"]):
                    first_correct = name
                    break

            #every client gets a persoanlised message according to their answer evaluation. every client gets it simultaneously
            for name, info in list(self.clients_dict.items()):
                if not info["connected"]:
                    continue

                sock = info["sock"]
                ans = answers.get(name)

                points_earned = 0
                
                if ans and ans["answer"] == correct:
                    points_earned += 1

                    if name == first_correct:
                        bonus = max(len(active_players) - 1, 0)
                        points_earned += bonus

                self.scoreboard[name] += points_earned

                if ans and ans["answer"] == correct:
                    if name == first_correct:
                        personal_msg = (
                            f"\nRESULTS FOR QUESTION {question_counter + 1}:\n"
                            f"Your answer was CORRECT.\n"
                            f"You were the FIRST player to answer correctly.\n"
                            f"Correct answer: {correct}\n"
                            f"Points earned: {points_earned}\n\n" )

                        server_ans_log = (f"{name} answered correctly and was first.") 
                    else:
                        personal_msg = (
                            f"\nRESULTS FOR QUESTION {question_counter + 1}:\n"
                            f"Your answer was CORRECT.\n"
                            f"You were NOT the FIRST player to answer correctly.\n"
                            f"Correct answer: {correct}\n"
                            f"Points earned: {points_earned}\n\n" )
                    
                        server_ans_log = (f"{name} answered correctly.")  
                else:
                    personal_msg = (
                        f"\nRESULTS FOR QUESTION {question_counter + 1}:\n"
                        f"Your answer was INCORRECT.\n"
                        f"You were NOT the first correct responder.\n"
                        f"Correct answer: {correct}\n"
                        f"Points earned: {points_earned}\n\n")
                    
                    server_ans_log = (f"{name} answered incorrectly.") 

                self.add_message_to_text(server_ans_log)

                try:
                    sock.send(personal_msg.encode())
                except:
                    if self.state == "RUNNING":
                        self.broadcast("A player has disconnected during the game.")
                    self.remove_client(sock, f"{name} disconnected during question results.")

            #now we broadcast the current scoreboard
            score_msg = "\nCURRENT SCOREBOARD:\n"
            for name, score in self.scoreboard.items():
                score_msg += name + ": " + str(score) + "\n"

            if self.state == "RUNNING" and question_counter + 1 < self.num_of_questions:
                self.broadcast(score_msg)
                self.add_message_to_text(score_msg.strip()) #also log it on the server

            question_counter += 1

            if one_player_remains:
                self.broadcast("Fewer than 2 players are on the server. Ending the game.")
                self.add_message_to_text("Fewer than 2 players are on the server. Ending the game.")
                break
            
        #temporary list of (name, score), sorted from highest to lowest score
        temp_rank = sorted(
        self.scoreboard.items(),
        key=lambda item: item[1],
        reverse=True)

        RANK_LIST = []

        first = True
        previous_score = None
        current_group = []

        for name, score in temp_rank:
            if first:
                current_group.extend([name, score])
                first = False
            elif score == previous_score:
                current_group.extend([name, score])
            else:
                RANK_LIST.append(current_group)
                current_group = [name, score]

            #update previous_score after processing this entry
            previous_score = score

        #add the last group
        if current_group:
            RANK_LIST.append(current_group)

        rank_msg = "\nFINAL RANKINGS:\n"

        rank_position = 1

        for group in RANK_LIST:
            rank_msg += str(rank_position) + ". "

            #number of players in this rank
            players_in_rank = len(group) // 2

            #if more than one player is in this rank (means a tie)
            if len(group) > 2:
                i = 0
                while i < len(group):
                    name = group[i]
                    score = group[i + 1]
                    rank_msg += name + " (" + str(score) + ")"
                    i += 2

                    if i < len(group):
                        rank_msg += ", " #add a comma to separate clients in the same ranking
            else:
                #only one player in this rank
                name = group[0]
                score = group[1]
                rank_msg += name + " (" + str(score) + ")"

            rank_msg += "\n"
            rank_position += players_in_rank #advance rank position by number of players occupying this rank

        #now we broadcast the final scoreboard
        score_msg = "\nFINAL SCOREBOARD:\n"
        for name, score in self.scoreboard.items():
            score_msg += name + ": " + str(score) + "\n"

        self.broadcast(score_msg)
        self.add_message_to_text(score_msg.strip()) #also log it on the server

        #also broadcast rankings to all clients
        self.broadcast(rank_msg)
        #log rankings on the server as well
        self.add_message_to_text(rank_msg.strip()) #also log it on the server

        self.broadcast("Game finished.") #notify players that game has ended
        self.add_message_to_text("Game finished.") #also log it on the server

        #disconnect all clients (server-initiated as game finished)
        for name, info in list(self.clients_dict.items()):
            if info["connected"]:
                self.remove_client(info["sock"])
            
        self.clients_dict.clear()
        
        #now go back to waiting and listening
        self.state = "WAITING"

    def reset_game(self):
        #resetting the game requires us to go back to waiting state
        self.is_resetting = True
        self.state = "WAITING"

        #clear all info from all variables and dcitionaries
        self.num_of_questions = 0
        self.questions = []
        self.scoreboard.clear()

        self.broadcast("RESETTING THE GAME")
        
        #disconnect all active clients cleanly (DO NOT stop listening)
        for name, info in list(self.clients_dict.items()):
            if not info["connected"]:
                continue
            try:
                info["sock"].send("Game reset by server. Disconnecting...".encode())
            except:
                pass

            time.sleep(0.05) #so that the client can receive the disconnection message before the socket closes
            self.remove_client(info["sock"])

        self.clients_dict.clear()

        #clear connected clients listbox (stop_listening removes clients, but be explicit)
        self.clients_listbox.config(state=tk.NORMAL)
        self.clients_listbox.delete(0, tk.END)
        self.clients_listbox.config(state=tk.DISABLED)

        #log and broadcast the reset action
        self.add_message_to_text("Game reset: server returned to WAITING state, all clients disconnected, game data cleared.")
        self.is_resetting = False


#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = GameServer(root)
    root.mainloop()