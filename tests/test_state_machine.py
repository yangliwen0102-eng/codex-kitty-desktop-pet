from __future__ import annotations

import unittest

from codex_pet.state_machine import EventKind, MonitorEvent, PetState, PetStateMachine


class PetStateMachineTests(unittest.TestCase):
    def test_requested_priority_order(self) -> None:
        machine = PetStateMachine(now=0)
        machine.set_hovered(True)
        self.assertEqual(machine.state, PetState.HOVER)

        machine.handle(MonitorEvent(EventKind.TASK_STARTED, "thread-a", occurred_at=1))
        self.assertEqual(machine.state, PetState.WORKING)

        machine.celebrating = True
        self.assertEqual(machine.state, PetState.COMPLETED)

        machine.failed = True
        self.assertEqual(machine.state, PetState.FAILED)

        machine.handle(
            MonitorEvent(
                EventKind.APPROVAL_REQUESTED,
                "thread-a",
                call_id="approval-a",
                occurred_at=2,
            )
        )
        self.assertEqual(machine.state, PetState.PERMISSION)

        machine.set_dragging(True)
        self.assertEqual(machine.state, PetState.DRAGGING)

        machine.begin_closing()
        self.assertEqual(machine.state, PetState.CLOSING)

    def test_task_lifecycle_and_completion_fallback(self) -> None:
        machine = PetStateMachine(now=0)
        machine.handle(MonitorEvent(EventKind.TASK_STARTED, "thread-a", occurred_at=1))
        machine.handle(MonitorEvent(EventKind.TASK_STARTED, "thread-b", occurred_at=2))
        machine.handle(MonitorEvent(EventKind.TASK_COMPLETED, "thread-a", occurred_at=3))
        self.assertEqual(machine.state, PetState.COMPLETED)

        machine.finish_animation(PetState.COMPLETED)
        self.assertEqual(machine.state, PetState.WORKING)

        machine.handle(MonitorEvent(EventKind.TASK_COMPLETED, "thread-b", occurred_at=4))
        machine.finish_animation(PetState.COMPLETED)
        self.assertEqual(machine.state, PetState.IDLE)

    def test_approval_resolves_to_working(self) -> None:
        machine = PetStateMachine(now=0)
        machine.handle(MonitorEvent(EventKind.TASK_STARTED, "thread-a", occurred_at=1))
        machine.handle(
            MonitorEvent(
                EventKind.APPROVAL_REQUESTED,
                "thread-a",
                call_id="call-a",
                occurred_at=2,
            )
        )
        self.assertEqual(machine.state, PetState.PERMISSION)
        machine.handle(
            MonitorEvent(
                EventKind.APPROVAL_RESOLVED,
                "thread-a",
                call_id="call-a",
                occurred_at=3,
            )
        )
        self.assertEqual(machine.state, PetState.WORKING)

    def test_boredom_and_activity_reset(self) -> None:
        machine = PetStateMachine(now=100)
        machine.update_boredom(now=699, timeout_seconds=600)
        self.assertEqual(machine.state, PetState.IDLE)
        machine.update_boredom(now=700, timeout_seconds=600)
        self.assertEqual(machine.state, PetState.BORED)
        machine.mark_activity(701)
        self.assertEqual(machine.state, PetState.IDLE)

    def test_failure_clears_on_new_task(self) -> None:
        machine = PetStateMachine(now=0)
        machine.handle(
            MonitorEvent(EventKind.TASK_FAILED, "thread-a", reason="quota", occurred_at=1)
        )
        self.assertEqual(machine.state, PetState.FAILED)
        machine.handle(MonitorEvent(EventKind.TASK_STARTED, "thread-b", occurred_at=2))
        self.assertEqual(machine.state, PetState.WORKING)


if __name__ == "__main__":
    unittest.main()
