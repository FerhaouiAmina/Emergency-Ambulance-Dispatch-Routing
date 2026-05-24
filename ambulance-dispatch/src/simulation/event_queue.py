import heapq


class EventQueue:
    def __init__(self):
        self.queue = []

    def push(self, event):
        heapq.heappush(self.queue, (event.timestamp, event))

    def pop(self):
        if self.is_empty():
            return None
        return heapq.heappop(self.queue)[1]

    def peek(self):
        if self.is_empty():
            return None
        return self.queue[0][1]

    def is_empty(self):
        return len(self.queue) == 0

    def size(self):
        return len(self.queue)

    def clear(self):
        self.queue.clear()

    def __repr__(self):
        return f"EventQueue(size={len(self.queue)})"