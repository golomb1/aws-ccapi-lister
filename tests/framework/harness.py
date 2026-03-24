"""Async orchestration helpers for policy tests."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import uuid4

from .contracts import PolicyContext
from .pulumi_runner import PulumiRunner


@dataclass
class TestHarness:
    __test__ = False
    project_name: str
    work_dir: str
    max_cloud_concurrency: int
    runner: PulumiRunner
    _semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.max_cloud_concurrency)

    async def run_blocking(self, fn, *args, **kwargs):
        """Run blocking cloud/Pulumi operation with bounded concurrency."""

        async with self._semaphore:
            return await asyncio.to_thread(fn, *args, **kwargs)

    def unique_stack_name(self, scenario: str) -> str:
        safe = scenario.replace(" ", "-").replace("_", "-")
        return f"{self.project_name}-{safe}-{uuid4().hex[:8]}"

    @asynccontextmanager
    async def isolated_stack(self, *, scenario: str, scope: str):
        """Create isolated ephemeral stack and always tear it down."""

        stack_name = self.unique_stack_name(scenario)
        stack = await self.run_blocking(
            self.runner.create_or_select_stack,
            stack_name=stack_name,
            project_name=self.project_name,
            work_dir=self.work_dir,
        )
        ctx = PolicyContext(
            project_name=self.project_name,
            work_dir=self.work_dir,
            stack_name=stack_name,
            scope=scope,
            metadata={"scenario": scenario},
        )
        try:
            yield ctx, stack
        finally:
            await self.run_blocking(self.runner.destroy, stack)
