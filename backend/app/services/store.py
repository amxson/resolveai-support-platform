"""In-memory ticket store for a zero-setup portfolio demo."""

from __future__ import annotations

from threading import RLock

from app.models import Ticket


class TicketStore:
    def __init__(self, tickets: list[Ticket]) -> None:
        self._lock = RLock()
        self._tickets = {ticket.id: ticket for ticket in tickets}
        self._counter = max(int(ticket.id.split("-")[-1]) for ticket in tickets) + 1

    def list(self) -> list[Ticket]:
        with self._lock:
            return sorted(self._tickets.values(), key=lambda ticket: ticket.created_at, reverse=True)

    def get(self, ticket_id: str) -> Ticket | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def next_id(self) -> str:
        with self._lock:
            ticket_id = f"TICK-{self._counter}"
            self._counter += 1
            return ticket_id

    def save(self, ticket: Ticket) -> Ticket:
        with self._lock:
            self._tickets[ticket.id] = ticket
            return ticket

