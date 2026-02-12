"""Shared utilities for tests."""


class AsyncIterator:
    """Helper to create an async iterator from a list."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self.iter = iter(self.items)  # pylint: disable=attribute-defined-outside-init
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration as e:
            raise StopAsyncIteration from e
