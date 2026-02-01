from typing import Protocol, Union, List
from memorymanager import Symbol


class Allocation(Protocol):
    @property
    def offset(self) -> int: ...


class Allocator(Protocol):
    def allocate_data(
        self,
        value: Union[int, float, str, bytes, Symbol, List[Union[int, float, Symbol]]],
        name: str,
        enforce_alignment: bool = True,
    ) -> Allocation: ...

    def allocate_empty(
        self, size: int, name: str, enforce_alignment: bool = True
    ) -> Allocation: ...
