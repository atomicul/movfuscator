from dataclasses import dataclass
from typing import List, Union, assert_never


class Allocation:
    """
    Represents a block of allocated memory.
    Use the factory methods `Allocation.data()` and `Allocation.empty()` to instantiate.
    """

    def __init__(self, name: str, offset: int, value: "InternalValueType"):
        self._name = name
        self._offset = offset
        self._value = value

    @classmethod
    def with_data(
        cls,
        name: str,
        offset: int,
        value: Union[int, float, str, List[Union[int, float]]],
    ) -> "Allocation":
        """Factory method to create a data-initialized allocation."""
        if isinstance(value, list) and not value:
            raise ValueError("Cannot allocate empty list")

        return cls(name, offset, value)

    @classmethod
    def empty(cls, name: str, offset: int, size: int) -> "Allocation":
        """Factory method to create an empty (uninitialized) allocation."""
        if size <= 0:
            raise ValueError("Size must be positive.")

        return cls(name, offset, EmptyValue(size))

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        """Calculates size based on the internal value type."""
        match self._value:
            case EmptyValue(size=s):
                return s
            case int() | float():
                return 4
            case str(v):
                return len(v) + 1
            case list(items):
                return len(items) * 4
            case x:
                assert_never(x)

    @property
    def directive(self) -> str:
        """Determines the assembly directive based on the internal value type."""
        match self._value:
            case EmptyValue():
                return ".zero"
            case int():
                return ".int"
            case float():
                return ".float"
            case str():
                return ".asciz"
            case list(items):
                # If any item is a float, the whole list is treated as floats
                if any(isinstance(x, float) for x in items):
                    return ".float"
                return ".int"
            case x:
                assert_never(x)

    def __str__(self) -> str:
        """Generates the assembly line."""
        val_str = self._format_value()
        comment = f" # {self._name} (+{self._offset})"

        return f"{self.directive} {val_str}{comment}"

    def _format_value(self) -> str:
        match self._value:
            case EmptyValue(size=s):
                return str(s)
            case int(v) | float(v):
                return str(v)
            case str(v):
                return f'"{v}"'
            case list(items):
                return ", ".join(str(x) for x in items)
            case x:
                assert_never(x)

    def __repr__(self) -> str:
        return f"Allocation(name='{self._name}', offset={self._offset}, value={self._value})"


InternalValueType = Union[int, float, str, List[Union[int, float]], "EmptyValue"]


@dataclass
class EmptyValue:
    """
    Internal class representing empty memory (padding or uninitialized blocks).
    Used to encapsulate the size when no actual data value exists.
    """

    size: int
