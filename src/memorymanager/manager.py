from typing import List, Optional, Union, assert_never
from .models import Allocation, AllocationDetails


class MemoryManager:
    """
    Manages the linear memory layout.
    """

    def __init__(self, master_label: str = "__MEMORY", alignment: int = 4):
        self.master_label = master_label
        self._alignment = alignment
        self._current_offset = 0
        self._allocations: List[AllocationDetails] = []

    def allocate_data(
        self,
        value: Union[int, float, str, List[Union[int, float]]],
        name: str = "",
    ) -> Allocation:
        """
        Allocates memory initialized with specific data.
        Returns an Allocation object with offset and size.
        """
        directive = ""
        initial_value_str = ""
        size = 0

        match value:
            case int(v):
                directive = ".int"
                size = 4
                initial_value_str = str(v)

            case float(v):
                directive = ".float"
                size = 4
                initial_value_str = str(v)

            case str(v):
                directive = ".asciz"
                size = len(v) + 1
                initial_value_str = f'"{v}"'

            case list(items):
                if not items:
                    raise ValueError(
                        "Cannot allocate empty list. Use allocate_empty instead."
                    )

                if any(type(x) is float for x in items):
                    directive = ".float"
                else:
                    directive = ".int"

                size = len(items) * 4
                initial_value_str = ", ".join(str(x) for x in items)

            case x:
                assert_never(x)

        return self._register_allocation(name, size, directive, initial_value_str)

    def allocate_empty(self, size: int, name: str) -> Allocation:
        """
        Reserves a block of zero-initialized memory.
        Returns an Allocation object with offset and size.
        """
        if size <= 0:
            raise ValueError("Size must be positive.")

        return self._register_allocation(name, size, ".zero", None)

    def _register_allocation(
        self,
        name: str,
        size: int,
        directive: str,
        initial_value_str: Optional[str],
    ) -> Allocation:
        """Internal helper to handle alignment and storage."""

        # --- Alignment Handling ---
        if self._current_offset % self._alignment != 0:
            padding = self._alignment - (self._current_offset % self._alignment)
            pad_name = f"__pad_{self._current_offset}"

            pad_alloc = AllocationDetails(
                name=pad_name,
                offset=self._current_offset,
                size=padding,
                directive=".zero",
            )
            self._allocations.append(pad_alloc)
            self._current_offset += padding

        # --- Registration ---
        offset = self._current_offset
        new_alloc = AllocationDetails(
            name=name,
            offset=offset,
            size=size,
            initial_value_str=initial_value_str,
            directive=directive,
        )
        self._allocations.append(new_alloc)
        self._current_offset += size

        return Allocation(offset=offset, size=size)

    def generate_data_section(self) -> str:
        lines = [
            ".section .data",
            f"{self.master_label}:",
        ]

        for alloc in self._allocations:
            desc = f" # {alloc.name} (+{alloc.offset})"

            if alloc.initial_value_str is None:
                # Empty allocation or padding
                lines.append(f"    .zero {alloc.size}{desc}")
            else:
                # Initialized data
                lines.append(f"    {alloc.directive} {alloc.initial_value_str}{desc}")

        return "\n".join(lines)
