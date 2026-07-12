from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class PetState(StrEnum):
    IDLE = "idle"
    HOVER = "hover"
    DRAGGING = "dragging"
    WORKING = "working"
    BORED = "bored"
    PERMISSION = "permission"
    COMPLETED = "completed"
    FAILED = "failed"
    CLOSING = "closing"


class EventKind(StrEnum):
    ACTIVITY = "activity"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_ABORTED = "task_aborted"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    TASK_FAILED = "task_failed"


@dataclass(frozen=True)
class MonitorEvent:
    kind: EventKind
    thread_id: str = ""
    call_id: str = ""
    reason: str = ""
    occurred_at: float = field(default_factory=time.time)


class PetStateMachine:
    """Pure state machine with the user-requested priority order."""

    def __init__(self, now: float | None = None) -> None:
        self.active_tasks: set[str] = set()
        self.pending_approvals: dict[str, str] = {}
        self.hovered = False
        self.dragging = False
        self.bored = False
        self.failed = False
        self.celebrating = False
        self.closing = False
        self.last_codex_activity = now if now is not None else time.time()

    @property
    def state(self) -> PetState:
        if self.closing:
            return PetState.CLOSING
        if self.dragging:
            return PetState.DRAGGING
        if self.pending_approvals:
            return PetState.PERMISSION
        if self.failed:
            return PetState.FAILED
        if self.celebrating:
            return PetState.COMPLETED
        if self.active_tasks:
            return PetState.WORKING
        if self.hovered:
            return PetState.HOVER
        if self.bored:
            return PetState.BORED
        return PetState.IDLE

    def handle(self, event: MonitorEvent) -> None:
        if event.kind is EventKind.ACTIVITY:
            self.mark_activity(event.occurred_at)
            return

        if event.kind is EventKind.TASK_STARTED:
            self.mark_activity(event.occurred_at)
            self.failed = False
            self.celebrating = False
            self.active_tasks.add(event.thread_id or "active")
            return

        if event.kind is EventKind.TASK_COMPLETED:
            self.mark_activity(event.occurred_at)
            self._finish_thread(event.thread_id)
            self.celebrating = True
            return

        if event.kind is EventKind.TASK_ABORTED:
            self.mark_activity(event.occurred_at)
            self._finish_thread(event.thread_id)
            return

        if event.kind is EventKind.APPROVAL_REQUESTED:
            self.mark_activity(event.occurred_at)
            key = event.call_id or f"approval:{event.thread_id}"
            self.pending_approvals[key] = event.thread_id
            return

        if event.kind is EventKind.APPROVAL_RESOLVED:
            self.mark_activity(event.occurred_at)
            if event.call_id:
                self.pending_approvals.pop(event.call_id, None)
            elif event.thread_id:
                self.pending_approvals = {
                    key: thread
                    for key, thread in self.pending_approvals.items()
                    if thread != event.thread_id
                }
            return

        if event.kind is EventKind.TASK_FAILED:
            self.mark_activity(event.occurred_at)
            self._finish_thread(event.thread_id)
            self.failed = True
            self.celebrating = False

    def mark_activity(self, occurred_at: float | None = None) -> None:
        self.last_codex_activity = occurred_at if occurred_at is not None else time.time()
        self.bored = False

    def update_boredom(self, now: float, timeout_seconds: int) -> None:
        if self.state in {
            PetState.CLOSING,
            PetState.DRAGGING,
            PetState.PERMISSION,
            PetState.FAILED,
            PetState.COMPLETED,
            PetState.WORKING,
        }:
            return
        self.bored = now - self.last_codex_activity >= timeout_seconds

    def set_hovered(self, hovered: bool) -> None:
        self.hovered = hovered

    def set_dragging(self, dragging: bool) -> None:
        self.dragging = dragging

    def begin_closing(self) -> None:
        self.closing = True

    def cancel_closing(self) -> None:
        self.closing = False

    def finish_animation(self, state: PetState) -> None:
        if state is PetState.COMPLETED:
            self.celebrating = False
        elif state is PetState.CLOSING:
            self.closing = False

    def _finish_thread(self, thread_id: str) -> None:
        if thread_id:
            self.active_tasks.discard(thread_id)
            self.pending_approvals = {
                key: thread
                for key, thread in self.pending_approvals.items()
                if thread != thread_id
            }
        else:
            self.active_tasks.clear()
            self.pending_approvals.clear()
