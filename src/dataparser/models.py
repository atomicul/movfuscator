from typing import Protocol, Union, List


class Allocation(Protocol):
    @property
    def offset(self) -> int: ...


class Allocator(Protocol):
    def allocate_data(
        self,
        value: Union[int, float, str, bytes, List[Union[int, float]]],
        name: str,
        enforce_alignment: bool = True,
    ) -> Allocation: ...

    def allocate_empty(
        self, size: int, name: str, enforce_alignment: bool = True
    ) -> Allocation: ...
