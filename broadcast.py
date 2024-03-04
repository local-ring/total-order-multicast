import time
import random
import threading
import heapq
import logging
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
                 UpHost, UpPort, 
                 DownHost, DownPort, 
                 commandsQueue):
        self.serverID = serverID
        self.commandsQueue = commandsQueue

        # set up socket for listening to the middleware layer
        self.ApplicationUpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ApplicationUpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ApplicationUpSocket.bind((UpHost, UpPort))
        self.ApplicationUpSocket.listen(1) # only allow one connection from the middleware layer

        self.toMiddlewareHost = DownHost
        self.toMiddlewarePort = DownPort


        self.logger = logging.getLogger('process{}'.format(self.serverID))
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler())
        self.logger.info('Process {} started'.format(self.serverID))
    
    def sendCommand(self, command):
        self.ApplicationDownSocket.sendall(command.encode())

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
        # wait for the middleware layer to connect
        try:
            middlewareSocket, addr = self.ApplicationUpSocket.accept()
            self.logger.info('Connected to {}'.format(addr))
        except Exception as e:
            self.logger.error('Could not connect to middleware layer')
            self.logger.error(e)
            return

        self.ApplicationDownSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ApplicationDownSocket.connect((self.toMiddlewareHost, self.toMiddlewarePort))
        
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
                self.logger.error('Unknown command: {}'.format(command[0]))
                print('Unknown command: {}'.format(command[0]))

            response = middlewareSocket.recv(1024)
            self.logger.info('Received response: {}'.format(response))
            print('Received response: {}'.format(response))



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
                applicationUpHost,
                applicationUpPort,
                applicationDownHost,
                applicationDownPort,
                networkUpHost,
                networkUpPort,
                networkDownHost,
                networkDownPort):
        
        self.serverID = serverID

        self.toApplicationHost = applicationUpHost
        self.toApplicationPort = applicationUpPort
        self.toNetworkHost = networkDownHost
        self.toNetworkPort = networkDownPort

        self.applicationDownSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.applicationDownSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.applicationDownSocket.bind((applicationDownHost, applicationDownPort))      
        self.applicationDownSocket.listen(1)



        self.networkUpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.networkUpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.networkUpSocket.bind((networkUpHost, networkUpPort))
        self.networkUpSocket.listen(1)

        self.balance = 1000   # initial balance of the bank account of some poor guy
        self.queue = [] # to store all messages received
        self.queueLock = threading.Lock() # to lock the queue
        self.acks = [] # to store all acks received
        self.acksLock = threading.Lock() # to lock the acks
        self.logicalTime = 0 # logical time of the server
        self.logicalTimeLock = threading.Lock() # to lock the logical time

        self.logger = logging.getLogger('process{}'.format(self.serverID))
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler())

    def listenApplication(self):
        """
        listen to the application layer
        """
        try:
            applicationSocket, addr = self.applicationDownSocket.accept()
            self.logger.info('Connected to {}'.format(addr))
        except Exception as e:
            self.logger.error('Could not connect to application layer')
            self.logger.error(e)
            return

        while 1:
            data = applicationSocket.recv(1024)
            message = data.decode()
            self.logger.info('Received message: {}'.format(message))
            print('Received message: {}'.format(message))
            self.multicast(message)

    def sendApplication(self, message):
        """
        send message to the application layer
        """
        self.applicationUpSocket.sendall(message.encode())

    def listenNetwork(self):
        """
        listen to the network layer
        """
        try:
            networkSocket, addr = self.networkUpSocket.accept()
            self.logger.info('Connected to {}'.format(addr))
        except Exception as e:
            self.logger.error('Could not connect to network layer')
            self.logger.error(e)
            return

        while 1:
            data = networkSocket.recv(1024)
            message = data.decode()
            self.logger.info('Received message: {}'.format(message))
            print('Received message: {}'.format(message))
            self.receive(message)

    def sendNetwork(self, message):
        """
        send message to the network layer
        """
        self.networkDownSocket.sendall(message.encode())

    def multicast(self, message):
        """
        multicast message to all processes
        """
        with self.logicalTimeLock:
            self.logicalTime += 1
            message = '{} {}'.format(self.logicalTime, message)

        self.sendNetwork(message)

    def receive(self, message):
        """
        receive message from the network layer
        """
        with self.queueLock:
            heapq.heappush(self.queue, message)
            self.logger.info('Added message to queue: {}'.format(message))
            print('Added message to queue: {}'.format(message))

        self.multicastAck(message)

    def multicastAck(self, message):
        """
        multicast ack to all processes
        """
        with self.logicalTimeLock:
            self.logicalTime += 1
            ack = '{} {}'.format(self.logicalTime, message)
        self.sendNetwork(ack)

    def deliver(self, message):
        """
        deliver message to the application layer
        """
        self.sendApplication(message)

    def listenAcks(self):
        """
        listen to the network layer for acks
        """
        try:
            networkSocket, addr = self.networkUpSocket.accept()
            self.logger.info('Connected to {}'.format(addr))
        except Exception as e:
            self.logger.error('Could not connect to network layer')
            self.logger.error(e)
            return

        while 1:
            data = networkSocket.recv(1024)
            ack = data.decode()
            self.logger.info('Received ack: {}'.format(ack))
            print('Received ack: {}'.format(ack))
            self.receiveAck(ack)

    def run(self):
        # connect to application layer with upstream and downstream sockets
        self.applicationUpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.applicationUpSocket.connect((self.toApplicationHost, self.toApplicationPort))

        # connect to network layer with upstream and downstream sockets
        self.networkDownSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.networkDownSocket.connect((self.toNetworkHost, self.toNetworkPort))

        # start all threads
        applicationThread = threading.Thread(target=self.listenApplication).start()
        networkThread = threading.Thread(target=self.listenNetwork).start()
        acksThread = threading.Thread(target=self.listenAcks).start()

        applicationThread.join()
        networkThread.join()
        acksThread.join()

    


"""
Network layer:
1. receive messages from middleware layer
2. send messages to middleware layer
"""
class Network:
    def __init__(self, serverList, thisServer):
        """
        serverList: list of (ID, UpHost, UpPort, DownHost, DownPort) tuples for all servers
        thisServer: (UpHost, UpPort, DownHost, DownPort) tuple for this server of the Network layer
        """
        self.serverUpList = [server[1:3] for server in serverList if server != thisServer]
        self.serverDownList = [server[3:] for server in serverList if server != thisServer]
        self.UpHost, self.UpPort, self.DownHost, self.DownPort = thisServer

        self.UpConnections = [] # to store all connections to other servers
        self.UpConnectionsLock = threading.Lock()
        self.DownConnections = [] # to store all connections from other servers
        self.DownConnectionsLock = threading.Lock() # to lock the connections list to prevent the race condition
        self.threads = []
        self.threadsLock = threading.Lock()

        self.logger = logging.getLogger('network') # create a logger for the network layer
        self.logger.setLevel(logging.DEBUG) # set the logging level to debug
        self.logger.addHandler(logging.StreamHandler()) # add a stream handler to the logger
        self.logger.info('Network started') # log that the network layer has started

        self.NetworkDownSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.NetworkDownSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print((self.DownHost, self.DownPort))
        self.NetworkDownSocket.bind((self.DownHost, self.DownPort))
        self.NetworkDownSocket.listen(len(serverList)) # we allow it to connect to all other servers
        self.NetworkDownSocket.settimeout(1)


    def accept(self):
        """
        connect to a server's middleware layer
        """
        try: 
            clientSocket, addr = self.NetworkDownSocket.accept()

            if addr not in self.serverDownList:
                self.logger.error('Connection from unknown server {}'.format(addr))
                return
            
            with self.DownConnectionsLock:
                self.DownConnections.append(clientSocket)
                self.logger.info('Connected to {}'.format(addr))
                print('Connected to {}'.format(addr))
            self.logger.info('Connected to {}'.format(addr))
            print('Connected to {}'.format(addr))

        except Exception as e:
            self.logger.error('Could not accept connection from {}'.format(addr))

    
    def broadcast(self, message):
        """
        broadcast a message to all servers' middleware layers
        """
        # before broadcasting, check if all connections are established
        for clientSocket in self.UpConnections:
            clientSocket.sendall(message.encode())
            self.logger.info('Sent message: {} to {}'.format(message, clientSocket.getpeername()))
            print('Sent message: {} to {}'.format(message, clientSocket.getpeername()))

    def handleClient(self, clientSocket):
        """
        receive messages from a server's middleware layer
        """
        try:
            while 1:
                data = clientSocket.recv(1024)
                message = data.decode()
                self.logger.info('Received message: {}'.format(message))
                print('Received message: {}'.format(message))
                self.broadcast(message)
        except Exception as e:
            self.logger.error('Error receiving message from {}'.format(clientSocket.getpeername()))
            self.logger.error(e)
        finally:
                clientSocket.close()

    def run(self):
        # wait for all connections (to the middleware) to be established
        while len(self.UpConnections) < len(self.serverUpList):
            for server in self.serverUpList:
                try:
                    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    clientSocket.connect(server)
                    with self.UpConnectionsLock:
                        self.UpConnections.append(clientSocket)
                except Exception as e:
                    self.logger.error('Could not connect to {}'.format(server))
                    self.logger.error(e)
                    time.sleep(1)
                    continue
        
        self.logger.info('All connections established')
        print('All connections established')

        for clientSocket in self.UpConnections:
            thread = threading.Thread(target=self.handleClient, args=(clientSocket,)).start()
            with self.threadsLock:
                self.threads.append(thread)

        for thread in self.threads:
            thread.join()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 broadcast.py <testcase> where testcase is the name of the testcase file like t1.json, t2.json, etc.')
        sys.exit(1)

    with open('./test/' + sys.argv[1], 'r') as f:
        data = json.load(f)

    network = data['network']
    networkUpHost = network['toMiddleware']['host']
    networkUpPort = network['toMiddleware']['port']
    networkDownHost = network['fromMiddleware']['host']
    networkDownPort = network['fromMiddleware']['port']

    # to store the connections between servers' middleware layers and network layers
    servers = data['servers']
    serverList = []
    for server in servers:
        serverID = server['serverID']
        toNetworkHost = server['Middleware']['toNetwork']['host']
        toNetworkPort = server['Middleware']['toNetwork']['port']
        fromNetworkHost = server['Middleware']['fromNetwork']['host']
        fromNetworkPort = server['Middleware']['fromNetwork']['port']
        serverList.append((serverID, fromNetworkHost, fromNetworkPort, toNetworkHost, toNetworkPort))

    # start the network layer
    print(serverList)
    print((networkUpHost, networkUpPort, networkDownHost, networkDownPort) )
    network = Network(serverList, (networkUpHost, networkUpPort, networkDownHost, networkDownPort))

    # start the middleware layer
    middlewares = []
    for server in servers:
        serverID = server['serverID']
        ApplicationUpHost = server['Middleware']['toApplication']['host']
        ApplicationUpPort = server['Middleware']['toApplication']['port']

        ApplicationDownHost = server['Middleware']['fromApplication']['host']
        ApplicationDownPort = server['Middleware']['fromApplication']['port']

        networkUpHost = server['Middleware']['toNetwork']['host']
        networkUpPort = server['Middleware']['toNetwork']['port']

        networkDownHost = server['Middleware']['fromNetwork']['host']
        networkDownPort = server['Middleware']['fromNetwork']['port']

        middleware = Middleware(serverID, 
                                ApplicationUpHost, ApplicationUpPort, ApplicationDownHost, ApplicationDownPort, 
                                networkUpHost, networkUpPort, networkDownHost, networkDownPort)
        middlewares.append(middleware)
        

    # start the application layer
    applications = []
    for server in servers:
        serverID = server['serverID']
        commandsQueue = server['commandsQueue']
        ApplicationUpHost = server['Application']['fromMiddleware']['host']
        ApplicationUpPort = server['Application']['fromMiddleware']['port']

        ApplicationDownHost = server['Application']['toMiddleware']['host']
        ApplicationDownPort = server['Application']['toMiddleware']['port']

        application = Application(serverID, 
                                ApplicationUpHost, ApplicationUpPort, ApplicationDownHost, ApplicationDownPort, 
                                commandsQueue)
        applications.append(application)

    # start all threads
    networkThread = threading.Thread(target=network.run).start()
    for middleware in middlewares:
        middlewareThread = threading.Thread(target=middleware.run).start()

    for application in applications:
        applicationThread = threading.Thread(target=application.run).start()

    # networkThread.join()
    # for middleware in middlewares:
    #     middlewareThread.join()
    # for application in applications:    
    #     applicationThread.join()

    # print('All threads joined')






    
