"""Long-term Store helpers — cross-thread user facts, namespace ("user", user_id).

Dev/test use InMemoryStore; prod uses AsyncPostgresStore (built in app/lifespan.py over
the same psycopg3 pool as the checkpointer, langgraph schema). (canonical-spec §3.6/§5)
"""
from __future__ import annotations

from langgraph.store.memory import InMemoryStore


def make_dev_store() -> InMemoryStore:
    return InMemoryStore()
