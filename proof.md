## Correctness of Totally Ordered Multicast

First, let's define the problem. We have a set of processes (in our specific implementation, servers of a bank system) that need to agree on the order of a set of messages received from application layers of all servers (operations like deposit at San Fransico and generate interest at New York). 

The messages are sent to the servers using a totally ordered multicast protocol, which guarantees that all messages are delivered to all servers in the same order. (The order of messages in the real world is not that important, that is, as long as all servers agree on the order of messages, the system is correct, even though the order of messages in the real world might be different.)

The algorithm is following:

- All messages timestamped with sender’s logical time
- Sender sends to all recipients, including itself
- When a message is received:
    1. It is put into a local queue
    2. Queue is ordered based on timestamp
    3. The acknowledgement is multicast to all servers

- Message is delivered to application only when both of the following conditions are met:
    1. It is at the head of the queue
    2. All the acknowledgement for that message have been received 

We also need extra assumptions:
- The network is reliable, that is, messages are not lost
- The network is FIFO, that is, messages are delivered in the order they are sent

Now, we need to prove that the algorithm is correct, that is, all servers agree on the order of messages.

### Proof
First, we reduce this case to pairs of servers (processes). If we can show that all pairs of servers agree on the order of messages, then we can show that all servers agree on the order of messages by the transitivity of the relation "agree on the order of messages".

So, it is enough to show that for every pair of servers, they agree on the order of messages.

We argue by contradiction. Suppose that the algorithm is not correct, that is, there is a case where a server A delivers a message (M, i) and server B delivers a message (N, j) instead at the same point of message sequence. Without loss of generality, we can assume that i < j. (Here M and N are the messages and i and j are the timestamps of the messages.)

In other words, we start comparing the message sequence of server A and server B from the beginning. The first umatched message is (M, i) and (N, j) and i < j. Before that, all messages are the same in both servers.

Since (N,j) is delivered, by protocol, server B received all acknowledgements for message (N,j), including the acknowledgement from server A. Meanwhile, all messages before are the same in both servers, this implies that (M, i) has not been delivered in server B. There are two possibilities:
- (M, i) is not at the head of the queue in server B
- (M, i) is at the head of the queue in server B, but not all acknowledgements for (M, i) have been received in server B

We can rule out the second possibility, because in this case, (N,j) is not the head of the queue and therefore it will NOT be delivered in server B according to the protocol. This contradicts the assumption that (N,j) is delivered in server B.

In the first case, it can only happen when B has not received (M,i), otherwise it will be in the head of queue due to i < j. 

Now suppose the message (M, i) was broadcasted by a server, say C (C can be A or B, for more general sake, we use letter C), and message (N, j) was broadcasted by a server, say D (again, D can be A or B). 

Since i < j, we know that C broadcasted (M, i) before it received (N, j) from D, otherwise, C will adjust its logical time to be greater than j which contradicts the assumption that i < j. It follows that acknowledgement for (N,j) was sent by C after it broadcasted (M, i). 

By FIFO message assumption, acknowledgement for (N,j) of server C will be received by B after (M, i) is received by B. In other words, B cannot receive all acknowledgements for (N, j) before it receives (M, i). So the first case is also impossible.