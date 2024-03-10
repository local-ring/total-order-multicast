import time
import random
import threading
import heapq
import sys
import os
import json
import socket
import signal


"""
Totally Ordered Multicast Algorithm Implementation 
(all acknowledgement multicast)

1. all messages timestamped with sender's logical time
2. all messages are sent to all processes, including the sender
3. when a message is received:
    - it is added to the local queue
    - the queue is sorted by timestamp
    - the ack is multicast to all processes with the receiver's logical time
4. message is delivered to application only when 
    - it is at the head of the queue
    - all acks for that message have been received

"""



"""
We use the bank server model:
- we have multiple bank servers (for simplicity, every server just store balance of one accout)
- each bank server has a application layer, middleware layer, and a network layer
- the application layer is the bank server itself, it will receive requests from clients and send responses
    requests include deposit, withdraw, interest (multiply by a number > 1), and balance
- the middleware layer is the totally ordered multicast algorithm implementation
- the network layer is the socket communication between bank servers
"""

"""
Application layer:
1. receive requests from clients (deposit, withdraw, interest, balance)
2. send requests to middleware layer
3. receive responses from middleware layer
4. send responses to clients
commandsQueue: a list of commands to be executed, such as
    [('deposit', 100), ('withdraw', 50), ('interest', 1.2)]

We will check the balance at the end. Since some operations are not commutative, the final balance will be most likely different if they are executed in different orders.
"""
shouldTerminate = threading.Event()
threads = []
threadsLock = threading.Lock()

class Application:
    def __init__(self, serverID, 
                 toMiddlewareAddr,
                 fromMiddlewareAddr,
                 commandsQueue):
        self.serverID = serverID
        self.balance = 1000 # we assume the initial balance of the bank account of some poor guy is 1000
        self.commands = [] # to store all commands delivered from the middleware layer

        thread = threading.Thread(target=self.listenfromMiddleware, args=(fromMiddlewareAddr,))
        with threadsLock:
            threads.append(thread)
        thread.start()
        

        self.commandsQueue = commandsQueue
        self.toMiddlewareAddr = toMiddlewareAddr
        # self.running = True
        signal.signal(signal.SIGINT, self.signalHandler)
    
    def signalHandler(self, sig, frame):
        print('You pressed Ctrl+C!')
        shouldTerminate.set()
        for thread in threads:
            thread.join()
        print('All threads joined')
        # sys.exit(0)

    def listenfromMiddleware(self, addr):
        """
        listen to the middleware layer
        """
        self.AppfromMiddlewareSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.AppfromMiddlewareSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.AppfromMiddlewareSocket.bind(addr)
        self.AppfromMiddlewareSocket.listen()
        print(f"Server-{self.serverID}'s application start listening from Middleware on port {addr}")

        while not shouldTerminate.is_set():
            sock, addr = self.AppfromMiddlewareSocket.accept()
            thread = threading.Thread(target=self.handleMiddleware, args=(sock, addr))
            with threadsLock:
                threads.append(thread)
            thread.start()

    def handleMiddleware(self, socket, addr):
        """
        handle messages from the middleware layer
        """
        while not shouldTerminate.is_set():
            data = socket.recv(1024)
            if not data:
                continue
            message = data.decode()
            print(f"Server-{self.serverID}'s application received message: {message}")
            message = message.split(':')
            operation, value = message[0], float(message[1])
            if operation == 'deposit':
                self.balance += value
            elif operation == 'withdraw':
                self.balance -= value
            elif operation == 'interest': 
                self.balance *= value
            else:
                print(f"Unknown operation: {operation} with value: {value}")
            
            self.commands.append((operation, value))
            # every time, when there is an update, write the balance to the file
            with open(f'Server{self.serverID}-log.txt', 'w') as f:
                f.write(f"Balance: {self.balance} after commands: {self.commands}")

    
    def sendtoMiddleware(self, addr):
        """
        send message to the middleware layer
        """

        for command in self.commandsQueue:  
            operation, value = command[0], command[1]
            command = f"{operation}:{value}"
            self.ApptoMiddlewareSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.ApptoMiddlewareSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.ApptoMiddlewareSocket.connect(addr)
            self.ApptoMiddlewareSocket.sendall(command.encode())

            print(f"Server-{self.serverID}'s application sent command to Middleware: {command}")
            # self.ApptoMiddlewareSocket.close()

    def run(self):
        self.sendtoMiddleware(self.toMiddlewareAddr)
        print(f"Server-{self.serverID}'s application sent all commands to Middleware")


"""
Middleware layer:
1. receive broadcast command from application layer
2. multicast message to all processes
3. receive messages from other processes
4. sort messages by timestamp
5. multicast ack to all processes
6. deliver message to application layer

We should have two(x2) sockets, one for communication with application layer and one for communication with network layer
"""
class Middleware:
    def __init__(self, 
                serverID,
                toApplicationAddr,
                fromApplicationAddr,
                toNetworkAddr,
                fromNetworkAddr,
                numServers):
        
        self.serverID = serverID

        self.toApplicationAddr = toApplicationAddr
        self.toNetworkAddr = toNetworkAddr 

        self.MiddltoApplicationSocket = None
        self.MiddletoNetworkSocket = None

        self.queue = [] # to store all messages received
        heapq.heapify(self.queue) # to sort the queue by timestamp
        self.queueLock = threading.Lock() # to lock the queue
        self.acks = {} # to store all acks received for each message, just record the number
        self.acksLock = threading.Lock() # to lock the acks
        self.lamportClock = 0 # the logical time of the server
        self.lamportClockLock = threading.Lock()

        thread = threading.Thread(target=self.listenfromApplication, args=(fromApplicationAddr,))
        with threadsLock:
            threads.append(thread)
        thread.start()

        thread = threading.Thread(target=self.listenfromNetwork, args=(fromNetworkAddr,))
        with threadsLock:
            threads.append(thread)

        thread = threading.Thread(target=self.processQueue, args=(numServers,),)
        with threadsLock:
            threads.append(thread)
        thread.start()

    
    def updateLamportClock(self, timestamp):
        """
        update the logical time of the server
        """
        with self.lamportClockLock:
            self.lamportClock = max(self.lamportClock, timestamp) + 1

    def listenfromApplication(self, addr):
        """
        listen from the application layer
        """
        self.MiddlefromApplicationSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MiddlefromApplicationSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.MiddlefromApplicationSocket.bind(addr)
        self.MiddlefromApplicationSocket.listen()
        print(f"Server-{self.serverID}'s Middleware start listening from Application on port {addr}")

        while not shouldTerminate.is_set():
            sock, addr = self.MiddlefromApplicationSocket.accept()

            thread = threading.Thread(target=self.handleApplication, args=(sock, addr))
            with threadsLock:
                threads.append(thread)
            thread.start()

    def handleApplication(self, socket, addr):
        """
        handle messages from the application layer
        """
        while not shouldTerminate.is_set():
            data = socket.recv(1024)
            if not data:
                continue
            message = data.decode()
            print(f'Server-{self.serverID} received message from Application: {message}') 
            message = message.split(':')
            operation, value = message[0], message[1]
            with self.lamportClockLock:
                self.lamportClock += 1
                # with self.queueLock:
                #     heapq.heappush(self.queue, (self.lamportClock, (operation, value)))
                self.sendtoNetwork(self.toNetworkAddr, f'{operation}:{value}:{self.lamportClock}\n') 
                print(f"Server-{self.serverID} sent message to Network: {operation}:{value}:{self.lamportClock}")

    def listenfromNetwork(self, addr):
        """
        listen from the network layer
        """
        self.MiddlefromNetworkSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MiddlefromNetworkSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.MiddlefromNetworkSocket.bind(addr)
        self.MiddlefromNetworkSocket.listen()
        print(f"Server-{self.serverID}'s Middleware start listening from Network on port {addr}")

        while not shouldTerminate.is_set():
            sock, addr = self.MiddlefromNetworkSocket.accept()

            thread = threading.Thread(target=self.handleNetwork, args=(sock, addr))
            with threadsLock:
                threads.append(thread)
            thread.start()
    
    def handleNetwork(self, socket, addr):
        """
        handle messages from the network layer
        """
        buffer = ''
        while not shouldTerminate.is_set():
            data = socket.recv(1024)
            if not data:
                continue
            data = data.decode()
            buffer += data
            messages = buffer.split('\n')
            buffer = messages.pop()
            for message in messages:
                print(f'Server{self.serverID} received message from Network: {message}')
                if message.startswith('ack'):
                    message = message.split(':')
                    operation, value, timestamp = message[1], message[2], message[3]

                    self.updateLamportClock(int(timestamp)) # update the logical time of the server because it is an event

                    with self.acksLock:
                        if (operation, value) in self.acks:
                            self.acks[(operation, value)] += 1
                        else:
                            self.acks[(operation, value)] = 1
                else:
                    message = message.split(':')
                    # print(message)
                    operation, value, timestamp = message[0], message[1], message[2]

                    self.updateLamportClock(int(timestamp))

                    with self.queueLock:
                        heapq.heappush(self.queue, (timestamp, (operation, value)))
                    with self.lamportClockLock:
                        self.lamportClock += 1
                    self.sendtoNetwork(self.toNetworkAddr, f'ack:{operation}:{value}:{self.lamportClock}\n')

    def processQueue(self, numServers):
        """
        process the queue and deliver messages to the application layer
        """
        while not shouldTerminate.is_set():
            with self.queueLock:
                if len(self.queue) > 0:
                    timestamp, (operation, value) = self.queue[0]
                    with self.acksLock:
                        if (operation, value) in self.acks and self.acks[(operation, value)] == numServers:
                            self.queue.pop(0)
                            self.acks.pop((operation, value))
                            self.sendtoApplication(self.toApplicationAddr, f'{operation}:{value}')
                # time.sleep(1)


    def sendtoApplication(self, addr, message):
        """
        deliver message to the application layer
        """
        with self.lamportClockLock:
            self.lamportClock += 1
        if self.MiddltoApplicationSocket is None:
            self.MiddltoApplicationSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.MiddltoApplicationSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.MiddltoApplicationSocket.connect(addr)

        self.MiddltoApplicationSocket.sendall(message.encode())
        print(f"Server-{self.serverID} sent message to Application: {message}")
            # self.MiddltoApplicationSocket.close()

    def sendtoNetwork(self, addr, message):
        """
        send message to the network layer so that it can be broadcasted
        """
        if self.MiddletoNetworkSocket is None:
            self.MiddltoNetworkSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.MiddltoNetworkSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.MiddltoNetworkSocket.connect(addr)

        self.MiddltoNetworkSocket.sendall(message.encode())
        print(f"Server {self.serverID} sent message to Network: {message[:-1]}") # not in the mood to print the newline character
        # self.MiddltoNetworkSocket.close()

    # def run(self):
    #     self.sendtoApplication(self.toApplicationAddr, 'Hello from Middleware')
    #     self.sendtoNetwork(self.toNetworkAddr, 'Hello from Middleware')
    

"""
Network layer:
1. receive messages from middleware layer
2. send messages to middleware layer
"""
class Network:
    def __init__(self, serverList,
                 fromMiddlewareAddr      
                 ):
        """
        serverList: list of (ID, fromNetworkHost, fromNetworkPort, toNetworkHost, toNetworkPort) tuples for all servers
        """
        self.serverList = serverList

        thread = threading.Thread(target=self.listenfromMiddleware, args=(fromMiddlewareAddr, len(serverList)))
        with threadsLock:
            threads.append(thread)
        thread.start()

        self.toConnections = {} # to store all connections to other servers
        self.toConnectionsLock = threading.Lock()
        self.fromConnections = [] # to store all connections from other servers
        self.fromConnectionsLock = threading.Lock() # to lock the connections list to prevent the race condition
        # self.threads = []
        # self.threadsLock = threading.Lock()

    def listenfromMiddleware(self, addr, numServers):
        """
        listen from the middleware layer
        """
        self.NetworkfromMiddlewareSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.NetworkfromMiddlewareSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.NetworkfromMiddlewareSocket.bind(addr)
        self.NetworkfromMiddlewareSocket.listen()
        print(f"Network start listening from Servers' Middleware on port {addr}")

        while not shouldTerminate.is_set():
            sock, addr = self.NetworkfromMiddlewareSocket.accept()
            with self.fromConnectionsLock:
                self.fromConnections.append(sock)
            thread = threading.Thread(target=self.handleMiddleware, args=(sock, addr))
            with threadsLock:
                threads.append(thread)
            thread.start()

    def handleMiddleware(self, socket, addr):
        """
        handle messages from the middleware layer
        """
        buffer = ''
        while not shouldTerminate.is_set():
            try:
                data = socket.recv(1024)
                if not data:
                    continue
                data = data.decode()
                buffer += data
                messages = buffer.split('\n')
                buffer = messages.pop()
                for message in messages:
                    print(f'Network layer received message: {message}')
                    for server in self.serverList:
                        serverID, fromNetworkHost, fromNetworkPort = server[0], server[1], server[2]
                        self.sendtoMiddleware(serverID, (fromNetworkHost, fromNetworkPort), message + '\n')
            except Exception as e:
                print(e)
            finally:
                break # the middleware idle for too long, means all messages are received

            
    def sendtoMiddleware(self, id, addr, message):
        """
        send message to the middleware layer
        """
        with self.toConnectionsLock:
            if id not in self.toConnections:
                self.toConnections[id] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.toConnections[id].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.toConnections[id].connect(addr)
                self.toConnections[id].sendall(message.encode())

            self.toConnections[id].sendall(message.encode())
            print(f"Network sent message to Server-{id}'s Middleware: {message[:-1]}") # not in the mood to print the newline character
        # NetworktoMiddlewareSocket.close()

    # def run(self):
    #     for middleware in self.serverList:
    #         middlewareID = middleware[0]
    #         toMiddlewareAddr = (middleware[1], middleware[2])
    #         self.sendtoMiddleware(middlewareID, toMiddlewareAddr, 'Hello from Network')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 broadcast.py <testcase> where testcase is the name of the testcase file like t1.json, t2.json, etc.')
        sys.exit(1)

    with open('./test/' + sys.argv[1], 'r') as f:
        data = json.load(f)

    servers = data['servers']
    numServers = len(servers)

    # start the application layer
    applications = []
    for server in servers:
        serverID = server['serverID']
        toMiddlewareHost = server['Application']['toMiddleware']['host']
        toMiddlewareHost = socket.gethostbyname(toMiddlewareHost)
        toMiddlewarePort = server['Application']['toMiddleware']['port']

        fromMiddlewareHost = server['Application']['fromMiddleware']['host']
        fromMiddlewareHost = socket.gethostbyname(fromMiddlewareHost)
        fromMiddlewarePort = server['Application']['fromMiddleware']['port']
        commandsQueue = server['commandsQueue']
        application = Application(serverID, 
                                  toMiddlewareAddr=(toMiddlewareHost, toMiddlewarePort),
                                  fromMiddlewareAddr=(fromMiddlewareHost, fromMiddlewarePort),
                                  commandsQueue=commandsQueue)
        applications.append(application)

    # start the middleware layer
    middlewares = []
    for server in servers:
        serverID = server['serverID']
        toApplicationHost = server['Middleware']['toApplication']['host']
        toApplicationHost = socket.gethostbyname(toApplicationHost)
        toApplicationPort = server['Middleware']['toApplication']['port']

        fromApplicationHost = server['Middleware']['fromApplication']['host']
        fromApplicationHost = socket.gethostbyname(fromApplicationHost)
        fromApplicationPort = server['Middleware']['fromApplication']['port']

        toNetworkHost = server['Middleware']['toNetwork']['host']
        toNetworkHost = socket.gethostbyname(toNetworkHost)
        toNetworkPort = server['Middleware']['toNetwork']['port']

        fromNetworkHost = server['Middleware']['fromNetwork']['host']
        fromNetworkHost = socket.gethostbyname(fromNetworkHost)
        fromNetworkPort = server['Middleware']['fromNetwork']['port']


        middleware = Middleware(serverID, 
                                toApplicationAddr=(toApplicationHost, toApplicationPort),
                                fromApplicationAddr=(fromApplicationHost, fromApplicationPort),
                                toNetworkAddr=(toNetworkHost, toNetworkPort),
                                fromNetworkAddr=(fromNetworkHost, fromNetworkPort),
                                numServers=numServers)
        middlewares.append(middleware)


    # start the network layer
    network = data['network']
    # toMiddlewareAddr = (network['toMiddleware']['host'], network['toMiddleware']['port'])
    fromMiddlewareAddr = (network['fromMiddleware']['host'], network['fromMiddleware']['port'])

    # to store the connections between servers' middleware layers and network layers

    serverList = []
    for server in servers:
        serverID = server['serverID']
        toNetworkHost = server['Middleware']['toNetwork']['host']
        toNetworkHost = socket.gethostbyname(toNetworkHost)
        toNetworkPort = server['Middleware']['toNetwork']['port']

        fromNetworkHost = server['Middleware']['fromNetwork']['host']
        fromNetworkHost = socket.gethostbyname(fromNetworkHost)
        fromNetworkPort = server['Middleware']['fromNetwork']['port']
        serverList.append((serverID, fromNetworkHost, fromNetworkPort, toNetworkHost, toNetworkPort))

    network = Network(serverList, fromMiddlewareAddr)

    time.sleep(2)
    for application in applications:
        application.run()
    # for middleware in middlewares:
    #     middleware.run()
    # network.run()

    # networkThread.join()
    # for middleware in middlewares:
    #     middlewareThread.join()
    # for application in applications:    
    #     applicationThread.join()

    # print('All threads joined')






    
