"""Small in-process cache. No questions or answers are written to disk."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
import time


class ResponseCache:
    def __init__(self, capacity=64, ttl=180, clock=time.monotonic):
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.items = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            item = self.items.get(key)
            if item is None:
                return None
            created, payload = item
            age = self.clock() - created
            if age >= self.ttl:
                del self.items[key]
                return None
            self.items.move_to_end(key)
            value = deepcopy(payload)
            value["cache"] = {"hit": True, "age_seconds": round(age, 2), "original_duration_ms": payload["duration_ms"]}
            return value

    def put(self, key, payload):
        with self.lock:
            self.items[key] = (self.clock(), deepcopy(payload))
            self.items.move_to_end(key)
            while len(self.items) > self.capacity:
                self.items.popitem(last=False)


responses = ResponseCache()
