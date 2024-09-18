import asyncio
import enum
import sys
from types import TracebackType
from typing import final

if sys.version_info >= (3, 11):
    from asyncio.timeouts import timeout as timeout

else:
    # ruff: noqa: S101

    class _State(enum.Enum):
        CREATED = "created"
        ENTERED = "active"
        EXPIRING = "expiring"
        EXPIRED = "expired"
        EXITED = "finished"

    @final
    class Timeout:
        def __init__(self, when: float | None) -> None:
            self._state = _State.CREATED
            self._timeout_handler: asyncio.Handle | None = None
            self._task: asyncio.Task | None = None
            if when is not None:
                when = asyncio.get_running_loop().time() + when
            self._when = when

        def when(self) -> float | None:
            return self._when

        def reschedule(self, when: float | None) -> None:
            if self._state is not _State.ENTERED:
                if self._state is _State.CREATED:
                    raise RuntimeError("Timeout has not been entered")
                raise RuntimeError(
                    f"Cannot change state of {self._state.value} Timeout",
                )

            self._when = when

            if self._timeout_handler is not None:
                self._timeout_handler.cancel()

            if when is None:
                self._timeout_handler = None
            else:
                loop = asyncio.get_running_loop()
                if when <= loop.time():
                    self._timeout_handler = loop.call_soon(self._on_timeout)
                else:
                    self._timeout_handler = loop.call_at(when, self._on_timeout)

        def expired(self) -> bool:
            return self._state in (_State.EXPIRING, _State.EXPIRED)

        def __repr__(self) -> str:
            info = [""]
            if self._state is _State.ENTERED:
                when = round(self._when, 3) if self._when is not None else None
                info.append(f"when={when}")
            info_str = " ".join(info)
            return f"<Timeout [{self._state.value}]{info_str}>"

        async def __aenter__(self) -> "Timeout":
            if self._state is not _State.CREATED:
                raise RuntimeError("Timeout has already been entered")
            task = asyncio.current_task()
            if task is None:
                raise RuntimeError("Timeout should be used inside a task")
            self._state = _State.ENTERED
            self._task = task
            self.reschedule(self._when)
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> bool | None:
            assert self._state in (_State.ENTERED, _State.EXPIRING)

            if self._timeout_handler is not None:
                self._timeout_handler.cancel()
                self._timeout_handler = None

            if self._state is _State.EXPIRING:
                self._state = _State.EXPIRED

                if exc_type is asyncio.CancelledError:
                    raise TimeoutError from exc_val
            elif self._state is _State.ENTERED:
                self._state = _State.EXITED

            return None

        def _on_timeout(self) -> None:
            assert self._state is _State.ENTERED
            assert self._task is not None
            self._task.cancel()
            self._state = _State.EXPIRING
            self._timeout_handler = None

    def timeout(delay: float | None) -> Timeout:
        return Timeout(delay)


__all__ = ["timeout"]
