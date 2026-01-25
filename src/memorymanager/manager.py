from typing import List, Union
from .allocation import Allocation


class MemoryManager:
    """
    Manages the linear memory layout.
    """

    def __init__(self, alignment: int = 4):
        self._alignment = alignment
        self._current_offset = 0
        self._allocations: List[Allocation] = []

    @property
    def allocations(self) -> List[Allocation]:
        """Returns the list of recorded allocations."""
        return self._allocations

    def allocate_data(
        self, value: "InputData", name: str = "", enforce_alignment: bool = True
    ) -> Allocation:
        """
        Allocates memory initialized with specific data.
        """
        if enforce_alignment:
            self._ensure_alignment()

        new_alloc = Allocation.with_data(name, self._current_offset, value)

        self._allocations.append(new_alloc)
        self._current_offset += new_alloc.size

        return new_alloc

    def allocate_empty(
        self, size: int, name: str, enforce_alignment: bool = True
    ) -> Allocation:
        """
        Reserves a block of zero-initialized memory.
        """
        if size <= 0:
            raise ValueError("Size must be positive.")

        if enforce_alignment:
            self._ensure_alignment()

        new_alloc = Allocation.empty(name, self._current_offset, size)

        self._allocations.append(new_alloc)
        self._current_offset += new_alloc.size

        return new_alloc

    def _ensure_alignment(self):
        """Internal helper to insert padding if the current offset is misaligned."""
        if self._current_offset % self._alignment != 0:
            padding_needed = self._alignment - (self._current_offset % self._alignment)
            pad_name = f"__pad_{self._current_offset}"

            pad_alloc = Allocation.empty(pad_name, self._current_offset, padding_needed)

            self._allocations.append(pad_alloc)
            self._current_offset += padding_needed


InputData = Union[int, float, str, bytes, List[Union[int, float]]]
