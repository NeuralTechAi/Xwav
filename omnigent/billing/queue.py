"""Bounded in-process inference queue with paid-request priority."""

from __future__ import annotations

import asyncio

from fastapi import HTTPException


class InferenceQueue:
    def __init__(self, capacity: int = 4, max_waiting: int = 32):
        self.capacity, self.max_waiting = capacity, max_waiting
        self.active = self.waiting = self.paid_waiting = 0
        self.condition = asyncio.Condition()

    async def acquire(self, paid: bool) -> None:
        async with self.condition:
            if self.waiting >= self.max_waiting:
                raise HTTPException(429, "Inference queue is full; retry shortly")
            self.waiting += 1
            self.paid_waiting += int(paid)
            try:
                async with asyncio.timeout(45):
                    await self.condition.wait_for(
                        lambda: self.active < self.capacity and (paid or not self.paid_waiting)
                    )
                self.active += 1
            except TimeoutError:
                raise HTTPException(429, "Inference queue timed out; retry shortly") from None
            finally:
                self.waiting -= 1
                self.paid_waiting -= int(paid)
                self.condition.notify_all()

    async def release(self) -> None:
        async with self.condition:
            self.active -= 1
            self.condition.notify_all()
