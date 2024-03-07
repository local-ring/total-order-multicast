## Totally Ordered Broadcast


### Structure

We use the bank model mentioned in the slide and the textbook: there are muliple servers in different places, say San Fransico, New York, etc. Each server has an application layer which send command like (deposit, 10), (interest, 1.2) to the middleware layer. Each middleware layer will send/receive message and acknowledgement to all other servers' middleware through the network layer (there is only one network layer in total).

The below diagram display the structure of the system:
TODO: A picture here

### Application Layer

The application layer is the top layer of the system. It is responsible for sending command to the middleware layer. The command is in the form of `(command, value)`. The command can be `deposit`, `withdraw`, `interest`, etc. The value is the amount of money or the interest rate. The application layer will send the command to the middleware layer and wait middleware layer to reorder the messages from other servers. Once the middleware find what it think is the message deliverable, it will send the message to the application layer. The application layer will then update the balance according to the message.

We can also track the history of message delivered to the application layer to see if the algorithm is correctly implemented.
Print the balance and the history of message delivered to the application layer when there is any change in the balance.

``` python
class ApplicationLayer:
    def __init__(self):
        self.balance = 1000
        self.commands = []
        thread(listenfromMiddleware)
    
    def listenfromMiddleware(self, message):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 10000))
        sock.listen(1)
        while 1:
            connection, client_address = sock.accept()
            try:
                while True:
                    data = connection.recv(16)
                    if data:
                        self.receiveMessagefromMiddleware(data)
                    else:
                        break
            finally:
                connection.close()

    def sendCommandtoMiddleware(self, command, value):
        for (command, value) in commands:
            message = (command, value)
            socket.send(message)

    def receiveMessagefromMiddleware(self, message):
        while 1:
            message = socket.recv()
            if message == ("deposit", value):
                self.balance += value 
            elif message == ("withdraw", value):
                self.balance -= value
            elif message == ("interest", value):
                self.balance *= value
            else:
                print("Invalid message")

            self.commands.append(message)
            printBalance()
    
    def printBalance(self):
        with open('Server-{ServerID}-log.txt', 'w') as f:
            f.write("Now the balance is", self.balance, "with the command", self.commands[-1])

```

### Middleware Layer

The middleware layer is the middle layer of the system. It is responsible for receiving command from the application layer and broadcast the command to all other servers through the network layer. It is also responsible for receiving message from the network layer and send the message to the application layer.

It will maintain a queue of messages received from the application layer and a queue of messages received from the network layer. It will deliver the message to the application layer only when 
1. The message is the first message in the queue of messages 
2. All acknowledgements for this message are received from all other servers' middleware layer

``` python
class Middleware:
    def __init__(self):
        self.messageQueue = []
        self.acknowledgement = {}
        self.lamportClock = 0
        thread(listenfromApplication)
        thread(listenfromNetwork)

    def updateLamportClock(self, message):
        self.lamportClock = max(self.lamportClock, message[1]) + 1

    def listenfromApplication(self, message):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 10001))
        sock.listen(1)
        while 1:
            connection, client_address = sock.accept()
            try:
                while True:
                    data = connection.recv(16)
                    if data:
                        self.receiveMessagefromApplication(data)
                    else:
                        break
            finally:
                connection.close()

    def listenfromNetwork(self, message):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 10002))
        sock.listen(1)
        while 1:
            connection, client_address = sock.accept()
            try:
                while True:
                    data = connection.recv(16)
                    if data:
                        self.receiveMessagefromNetwork(data)
                    else:
                        break
            finally:
                connection.close()

    def sendMessagetoNetwork(self, message):
        self.lamportClock += 1
        message = (message, self.lamportClock)
        socket.send(message)

    def sendAcknowledgementtoNetwork(self, message):
        self.lamportClock += 1
        message = "ack:" + message
        message = (message, self.lamportClock)
        socket.send(message)

    def isacknowledgement(self, message):
        message = message[0]
        message = message.split(":")
        if message[0] == "ack":
            return True
        else:
            return False

    def receiveMessagefromApplication(self, message):
        self.lamportClock += 1
        self.messageQueue.append(message)
        self.sendMessagetoNetwork(message)
    
    def receiveMessagefromNetwork(self, message):
        self.updateLamportClock(message)
        if isacknowledgement(message):
            self.acknowledgement[message] += 1
        else:
            self.messageQueue.append(message)
            self.sendAcknowledgementtoNetwork(message)

    def processQueue(self, number_of_servers):
        while 1:
            if self.messageQueue:
                message = self.messageQueue[0]
                if self.acknowledgement[message]== number_of_servers-1:
                    self.deliverMessage(message)

    def deliverMessage(self, message):
        self.lamportClock += 1
        self.messageQueue.pop(0)
        del self.acknowledgement[message]
        sendMessagetoApplication(message)
```

### Network Layer

The network layer is the bottom layer of the system. It is responsible for sending message to all other servers' middleware layer and receive message from all other servers' middleware layer. It is also responsible for sending acknowledgement to all other servers' middleware layer and receive acknowledgement from all other servers' middleware layer.

``` python
def listenfromMiddleware(self, message):
    while 1:
        message = socket.recv()
        multicast(message)

def multicast(self, message):
    for server in servers:
        socket.send(server, message)
```
