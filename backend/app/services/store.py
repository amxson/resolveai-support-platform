"""In-memory ticket store for a zero-setup portfolio demo."""

from __future__ import annotations

from threading import RLock

from app.models import Ticket


class StoreFullError(ValueError):
    pass


class TicketStore:
    def __init__(self, tickets: list[Ticket], max_tickets: int = 500) -> None:
        self._lock = RLock()
        self._max_tickets = max_tickets
        self._tickets = {ticket.id: ticket for ticket in tickets}
        self._counter = (
            max((int(ticket.id.split("-")[-1]) for ticket in tickets), default=0) + 1
        )

    def list(self) -> list[Ticket]:
        with self._lock:
            return [
                ticket.model_copy(deep=True)
                for ticket in sorted(
                    self._tickets.values(),
                    key=lambda ticket: ticket.created_at,
                    reverse=True,
                )
            ]

    def get(self, ticket_id: str) -> Ticket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            return ticket.model_copy(deep=True) if ticket else None

    def ensure_capacity(self) -> None:
        with self._lock:
            if len(self._tickets) >= self._max_tickets:
                raise StoreFullError("Demo ticket capacity reached.")

    def next_id(self) -> str:
        with self._lock:
            ticket_id = f"TICK-{self._counter}"
            self._counter += 1
            return ticket_id

    def save(self, ticket: Ticket) -> Ticket:
        with self._lock:
            if (
                ticket.id not in self._tickets
                and len(self._tickets) >= self._max_tickets
            ):
                raise StoreFullError("Demo ticket capacity reached.")
            self._tickets[ticket.id] = ticket.model_copy(deep=True)
            return ticket
