"""SchedulerBridge — APScheduler 3.x bridge with Nodus host function registration."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any, Callable

_AVAILABLE = importlib.util.find_spec("apscheduler") is not None

if TYPE_CHECKING:
    from apscheduler.job import Job
    from nodus.runtime.embedding import NodusRuntime


class SchedulerBridge:
    """APScheduler bridge for interval and cron job management.

    Requires ``nodus-sdk[scheduler]`` (``apscheduler>=3.10``).

    Usage::

        bridge = SchedulerBridge()
        bridge.register_job("reports.nightly", run_nightly_report)   # host-side callable
        bridge.start()
        rt.attach_scheduler(bridge)
        # .nd: scheduler_add_interval("my.job", 60, "reports.nightly")
        # .nd: scheduler_cancel("my.job")

    A ``.nd`` program schedules work by naming a job the host registered with
    :meth:`register_job` (#5). The callback runs host-side on an APScheduler
    thread, where re-entering the VM would not be safe; the host decides what
    a name does. A name nothing registered is refused at scheduling time,
    not scheduled as a no-op.
    """

    def __init__(
        self,
        *,
        jobstore_url: str | None = None,
        timezone: str = "UTC",
        max_workers: int = 10,
    ) -> None:
        if not _AVAILABLE:
            raise ImportError("apscheduler not installed. pip install nodus-sdk[scheduler]")
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.executors.pool import ThreadPoolExecutor

        jobstores: dict[str, Any] = {}
        if jobstore_url:
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
            jobstores["default"] = SQLAlchemyJobStore(url=jobstore_url)

        self._scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors={"default": ThreadPoolExecutor(max_workers)},
            timezone=timezone,
        )
        self._started = False
        self._jobs: dict[str, Callable[[], Any]] = {}

    def register_job(self, name: str, fn: Callable[[], Any]) -> "SchedulerBridge":
        """Make *fn* schedulable from ``.nd`` under *name* (#5).

        The only path from a Nodus program to real scheduled work. Before this
        the ``scheduler_add_*`` builtins scheduled ``lambda: None``: the job id
        came back, the job listed, ``next_run`` advanced, and nothing ever ran.
        """
        if not callable(fn):
            raise TypeError(f"register_job({name!r}): fn must be callable, got {type(fn).__name__}")
        self._jobs[name] = fn
        return self

    def registered_jobs(self) -> list[str]:
        return sorted(self._jobs)

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True

    def shutdown(self, wait: bool = True) -> None:
        if self._started:
            self._scheduler.shutdown(wait=wait)
            self._started = False

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        *,
        seconds: int,
        replace_existing: bool = True,
        **kwargs: Any,
    ) -> "Job":
        return self._scheduler.add_job(
            func,
            "interval",
            id=job_id,
            seconds=seconds,
            replace_existing=replace_existing,
            **kwargs,
        )

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        *,
        cron_expr: str,
        replace_existing: bool = True,
        **kwargs: Any,
    ) -> "Job":
        parts = cron_expr.strip().split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
        else:
            minute, hour, day, month, day_of_week = "*", "*", "*", "*", "*"
        return self._scheduler.add_job(
            func,
            "cron",
            id=job_id,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            replace_existing=replace_existing,
            **kwargs,
        )

    def cancel(self, job_id: str) -> bool:
        try:
            self._scheduler.remove_job(job_id)
            return True
        except Exception:
            return False

    def list_jobs(self) -> list[dict]:
        return [
            {"id": j.id, "name": j.name or j.id, "next_run": str(j.next_run_time)}
            for j in self._scheduler.get_jobs()
        ]

    def register_host_functions(self, runtime: "NodusRuntime") -> None:
        """Register scheduler_add_interval, scheduler_add_cron, scheduler_cancel, scheduler_list_jobs."""
        bridge = self

        def _resolve(job: Any) -> Callable[[], Any] | str:
            if not isinstance(job, str):
                return "error:invalid_job"
            fn = bridge._jobs.get(job)
            if fn is None:
                known = ", ".join(bridge.registered_jobs()) or "none"
                return f"error:unknown job {job!r}; register it host-side with SchedulerBridge.register_job (registered: {known})"
            return fn

        def scheduler_add_interval(job_id: Any, seconds: Any, job: Any) -> str:
            if not isinstance(job_id, str):
                return "error:invalid_job_id"
            secs = int(seconds) if isinstance(seconds, (int, float)) else 60
            fn = _resolve(job)
            if isinstance(fn, str):
                return fn
            try:
                bridge.add_interval_job(job_id, fn, seconds=secs)
                return job_id
            except Exception as exc:
                return f"error:{exc}"

        def scheduler_add_cron(job_id: Any, cron_expr: Any, job: Any) -> str:
            if not isinstance(job_id, str) or not isinstance(cron_expr, str):
                return "error:invalid_args"
            fn = _resolve(job)
            if isinstance(fn, str):
                return fn
            try:
                bridge.add_cron_job(job_id, fn, cron_expr=cron_expr)
                return job_id
            except Exception as exc:
                return f"error:{exc}"

        def scheduler_cancel(job_id: Any) -> bool:
            if not isinstance(job_id, str):
                return False
            return bridge.cancel(job_id)

        def scheduler_list_jobs() -> list:
            return bridge.list_jobs()

        runtime.register_function("scheduler_add_interval", scheduler_add_interval, arity=3)
        runtime.register_function("scheduler_add_cron", scheduler_add_cron, arity=3)
        runtime.register_function("scheduler_cancel", scheduler_cancel, arity=1)
        runtime.register_function("scheduler_list_jobs", scheduler_list_jobs, arity=0)

    @property
    def scheduler(self) -> Any:
        return self._scheduler
