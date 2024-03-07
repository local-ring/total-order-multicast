import time
import random
import threading
import heapq
import sys
import os
import json
import socket


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
    [('deposit', 100), ('withdraw', 50), ('interest', 1.2), ('balance')]
"""

class Application:
    def __init__(self, serverID, 
                 toMiddlewareAddr,
                 fromMiddlewareAddr,
                 commandsQueue):
        self.serverID = serverID
        threading.Thread(target=self.listenfromMiddleware, args=(fromMiddlewareAddr,)).start()

        self.commandsQueue = commandsQueue
        self.toMiddlewareAddr = toMiddlewareAddr

    def listenfromMiddleware(self, addr):
        """
        listen to the middleware layer
        """
        self.AppfromMiddlewareSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.AppfromMiddlewareSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.AppfromMiddlewareSocket.bind(addr)
        self.AppfromMiddlewareSocket.listen()
        print(f"Server {self.serverID}'s application start listening from Middleware on port {addr}")

        while 1:
            sock, addr = self.AppfromMiddlewareSocket.accept()
            threading.Thread(target=self.handleMiddleware, args=(sock, addr)).start()

    def handleMiddleware(self, socket, addr):
        """
        handle messages from the middleware layer
        """
        while 1:
            data = socket.recv(1024)
            message = data.decode()
            print(f"Server {self.serverID}'s application received message: {message}")
    
        # TODO: figure out what to do with the message
    
    def sendtoMiddleware(self, addr, message):
        """
        send message to the middleware layer
        """
        self.ApptoMiddlewareSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Connecting to {addr}")
        self.ApptoMiddlewareSocket.connect(addr)
        self.ApptoMiddlewareSocket.sendall(message.encode())
        print(f"Server {self.serverID}'s application sent message to Middleware: {message}")
        self.ApptoMiddlewareSocket.close()

    
    def sendCommand(self, command):
        self.sendtoMiddleware(self.toMiddlewareAddr, command)

    def deposit(self, amount):
        message = 'deposit {}'.format(amount)
        self.sendCommand(message)
    
    def withdraw(self, amount):
        message = 'withdraw {}'.format(amount)
        self.sendCommand(message)

    def interest(self, rate):
        message = 'interest {}'.format(rate)
        self.sendCommand(message)

    def balance(self):
        message = 'balance'
        self.sendCommand(message)

    def run(self):
        for command in self.commandsQueue:
            if command[0] == 'deposit':
                self.deposit(command[1])
            elif command[0] == 'withdraw':
                self.withdraw(command[1])
            elif command[0] == 'interest':
                self.interest(command[1])
            elif command[0] == 'balance':
                self.balance()
            else:
                print('Unknown command: {}'.format(command[0]))


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
                fromNetworkAddr):
        
        self.serverID = serverID

        threading.Thread(target=self.listenfromApplication, args=(fromApplicationAddr,)).start()
        threading.Thread(target=self.listenfromNetwork, args=(fromNetworkAddr,)).start()

        self.toApplicationAddr = toApplicationAddr
        self.toNetworkAddr = toNetworkAddr 


        self.balance = 1000   # initial balance of the bank account of some poor guy
        self.queue = [] # to store all messages received
        self.queueLock = threading.Lock() # to lock the queue
        self.acks = [] # to store all acks received
        self.acksLock = threading.Lock() # to lock the acks
        self.logicalTime = 0 # logical time of the server
        self.logicalTimeLock = threading.Lock() # to lock the logical time


    def listenfromApplication(self, addr):
        """
        listen from the application layer
        """
        self.MiddlefromApplicationSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MiddlefromApplicationSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.MiddlefromApplicationSocket.bind(addr)
        self.MiddlefromApplicationSocket.listen()
        print(f"Server {self.serverID}'s Middleware start listening from Application on port {addr}")

        while 1:
            sock, addr = self.MiddlefromApplicationSocket.accept()
            threading.Thread(target=self.handleApplication, args=(sock, addr)).start()

    def handleApplication(self, socket, addr):
        """
        handle messages from the application layer
        """
        while 1:
            data = socket.recv(1024)
            message = data.decode()
            print('Received message: {}'.format(message))
            # self.multicast(message)
            # TODO: figure out what to do with the message

    def listenfromNetwork(self, addr):
        """
        listen from the network layer
        """
        self.MiddlefromNetworkSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MiddlefromNetworkSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.MiddlefromNetworkSocket.bind(addr)
        self.MiddlefromNetworkSocket.listen()
        print(f"Server {self.serverID}'s Middleware start listening from Network on port {addr}")

        while 1:
            sock, addr = self.MiddlefromNetworkSocket.accept()
            threading.Thread(target=self.handleNetwork, args=(sock, addr)).start()
    
    def handleNetwork(self, socket, addr):
        """
        handle messages from the network layer
        """
        while 1:
            data = socket.recv(1024)
            message = data.decode()
            print('Received message: {}'.format(message))
            # self.multicast(message)


    def sendtoApplication(self, addr, message):
        """
        send message to the application layer
        """
        self.MiddltoApplicationSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MiddltoApplicationSocket.connect(addr)
        self.MiddltoApplicationSocket.sendall(message.encode())
        print(f"Server {self.serverID} sent message to Application: {message}")
        self.MiddltoApplicationSocket.close()

    def sendtoNetwork(self, addr, message):
        """
        send message to the network layer
        """
        self.MiddltoNetworkSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.MiddltoNetworkSocket.connect(addr)
        self.MiddltoNetworkSocket.sendall(message.encode())
        print(f"Server {self.serverID} sent message to Network: {message}")
        self.MiddltoNetworkSocket.close()

    def run(self):
        self.sendtoApplication(self.toApplicationAddr, 'Hello from Middleware')
        self.sendtoNetwork(self.toNetworkAddr, 'Hello from Middleware')
    

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

        threading.Thread(target=self.listenfromMiddleware, args=(fromMiddlewareAddr, len(serverList))).start()

        self.toConnections = [] # to store all connections to other servers
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
        self.NetworkfromMiddlewareSocket.listen(numServers)
        print(f"Network start listening from Servers' Middleware on port {addr}")

        while 1:
            sock, addr = self.NetworkfromMiddlewareSocket.accept()
            with self.fromConnectionsLock:
                self.fromConnections.append(sock)
            threading.Thread(target=self.handleMiddleware, args=(sock, addr)).start()

    def handleMiddleware(self, socket, addr):
        """
        handle messages from the middleware layer
        """
        while 1:
            data = socket.recv(1024)
            message = data.decode()
            print('Received message: {}'.format(message))
            
    def sendtoMiddleware(self, id, addr, message):
        """
        send message to the middleware layer
        """
        self.NetworktoMiddlewareSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.NetworktoMiddlewareSocket.connect(addr)
        self.NetworktoMiddlewareSocket.sendall(message.encode())
        print(f"Network sent message to Server {id}'s Middleware: {message}")
        self.NetworktoMiddlewareSocket.close()

    def run(self):
        for middleware in self.serverList:
            middlewareID = middleware[0]
            toMiddlewareAddr = (middleware[1], middleware[2])
            self.sendtoMiddleware(middlewareID, toMiddlewareAddr, 'Hello from Network')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 broadcast.py <testcase> where testcase is the name of the testcase file like t1.json, t2.json, etc.')
        sys.exit(1)

    with open('./test/' + sys.argv[1], 'r') as f:
        data = json.load(f)

    servers = data['servers']

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
                                fromNetworkAddr=(fromNetworkHost, fromNetworkPort))
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
    for middleware in middlewares:
        middleware.run()
    network.run()

    # networkThread.join()
    # for middleware in middlewares:
    #     middlewareThread.join()
    # for application in applications:    
    #     applicationThread.join()

    # print('All threads joined')






    
