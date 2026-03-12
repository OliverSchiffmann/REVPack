class World:
    _now: int

    def __init__(self) -> None:
        self._now = 0

    def now(self) -> int:
        return self._now
