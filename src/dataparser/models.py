from typing import Protocol, Union, List


class Allocation(Protocol):
    @property
    def offset(self) -> int: ...


class Allocator(Protocol):
    def allocate_data(
        self, value: Union[int, float, str, List[Union[int, float]]], name: str
    ) -> Allocation: ...

    def allocate_empty(self, size: int, name: str) -> Allocation: ...
