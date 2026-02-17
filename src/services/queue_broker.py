"""Queue broker scaffolding for horizontal workers.

Baseline implementation:
- `InMemoryQueueBroker` for local/dev.
- `RedisQueueBroker` placeholder for production rollout.
"""

from __future__ import annotations

import json
import os
import queue
from dataclasses import dataclass
from typing import Any, Protocol


class QueueBroker(Protocol):
    def enqueue(self, topic: str, payload: dict[str, Any]) -> None: ...

    def dequeue(self, topic: str, timeout_seconds: int = 1) -> dict[str, Any] | None: ...


@dataclass
class InMemoryQueueBroker:
    _queues: dict[str, queue.Queue]

    def __init__(self) -> None:
        self._queues = {}

    def _get_q(self, topic: str) -> queue.Queue:
        if topic not in self._queues:
            self._queues[topic] = queue.Queue()
        return self._queues[topic]

    def enqueue(self, topic: str, payload: dict[str, Any]) -> None:
        self._get_q(topic).put(payload)

    def dequeue(self, topic: str, timeout_seconds: int = 1) -> dict[str, Any] | None:
        try:
            return self._get_q(topic).get(timeout=timeout_seconds)
        except queue.Empty:
            return None


@dataclass
class RedisQueueBroker:
    redis_url: str

    def __post_init__(self) -> None:
        import redis  # type: ignore

        self._client = redis.Redis.from_url(self.redis_url)

    def enqueue(self, topic: str, payload: dict[str, Any]) -> None:
        self._client.rpush(topic, json.dumps(payload, ensure_ascii=False))

    def dequeue(self, topic: str, timeout_seconds: int = 1) -> dict[str, Any] | None:
        item = self._client.blpop(topic, timeout=timeout_seconds)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)


def get_queue_broker() -> QueueBroker:
    backend = os.getenv("QUEUE_BROKER_BACKEND", "memory").lower()
    if backend == "redis":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return RedisQueueBroker(redis_url=redis_url)
    return InMemoryQueueBroker()


queue_broker = get_queue_broker()
