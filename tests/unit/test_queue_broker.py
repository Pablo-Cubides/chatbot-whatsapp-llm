from src.services.queue_broker import InMemoryQueueBroker


def test_in_memory_queue_broker_roundtrip() -> None:
    broker = InMemoryQueueBroker()

    broker.enqueue("events", {"id": "evt_1", "value": 42})
    payload = broker.dequeue("events", timeout_seconds=1)

    assert payload is not None
    assert payload["id"] == "evt_1"
    assert payload["value"] == 42


def test_in_memory_queue_broker_empty_returns_none() -> None:
    broker = InMemoryQueueBroker()

    payload = broker.dequeue("missing", timeout_seconds=1)

    assert payload is None
