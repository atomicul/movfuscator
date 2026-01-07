from dataclasses import dataclass
from typing import List, Union

from dataparser import parse_data

# --- Stubs and Mocks ---


@dataclass
class DummyAllocation:
    """A simple concrete implementation of the Allocation protocol for testing."""

    offset: int
    size: int


class StubMemoryManager:
    """
    A stub implementation of the Allocator protocol.
    1. Reports function calls for verification.
    2. Returns distinct dummy objects to verify structural integrity.
    """

    def __init__(self):
        self.calls: List[tuple] = []
        self._allocation_counter = 0

    def _create_dummy(self) -> DummyAllocation:
        """Generates a unique dummy allocation."""
        self._allocation_counter += 1
        # Assign arbitrary offset/size based on counter to distinguish objects
        return DummyAllocation(offset=self._allocation_counter * 10, size=4)

    def allocate_data(
        self, value: Union[int, float, str, List[Union[int, float]]], name: str
    ) -> DummyAllocation:
        self.calls.append(("allocate_data", value, name))
        return self._create_dummy()

    def allocate_empty(self, size: int, name: str) -> DummyAllocation:
        self.calls.append(("allocate_empty", size, name))
        return self._create_dummy()


# --- Test Cases ---


def test_parse_data_call_order_and_parameters():
    """
    Verifies that the parser calls the allocator methods in the correct order
    with the correct parsed parameters, handling various directives and labels.
    """
    stub = StubMemoryManager()

    # A mix of directives, labels, comments, and multiple values
    source_code = """
    .section .data
    .float 3.14

    var_int: .int 42
        .long 10, 20      # List of ints
        
    var_str:
        .asciz "Hello"
        
    # A comment line that should be ignored
    var_empty:
        .zero 16// Inline comment
        .skip 32
        
    """

    parse_data(stub, source_code)

    expected_calls = [
        # 1. Anonymous float at the start
        ("allocate_data", 3.14, "__anonymous_data"),
        # 2. Integer 42 under var_int
        ("allocate_data", 42, "var_int"),
        # 3. List of ints under var_int
        ("allocate_data", [10, 20], "var_int"),
        # 4. String under var_str
        ("allocate_data", "Hello", "var_str"),
        # 5. Zero padding under var_empty
        ("allocate_empty", 16, "var_empty"),
        # 6. Skip padding under var_empty
        ("allocate_empty", 32, "var_empty"),
    ]

    assert stub.calls == expected_calls


def test_parse_data_return_structure():
    """
    Verifies that the parser returns the correct hierarchy of DataLabel objects
    and that these objects contain the exact Allocation instances returned by the allocator.
    """
    stub = StubMemoryManager()

    source_code = """
    .data
    label_one:
        .int 1
    
    label_two:
        .float 2.0
        .space 10
    """

    labels = parse_data(stub, source_code)

    # Verify keys exist
    assert "label_one" in labels
    assert "label_two" in labels

    # Verify label_one structure
    # Should correspond to the 1st allocation created by the stub (offset=10)
    allocs_one = labels["label_one"]
    assert len(allocs_one) == 1
    assert isinstance(allocs_one[0], DummyAllocation)
    assert allocs_one[0].offset == 10

    # Verify label_two structure
    allocs_two = labels["label_two"]
    assert len(allocs_two) == 2

    # Should correspond to 2nd allocation (offset=20)
    assert allocs_two[0].offset == 20
    # Should correspond to 3rd allocation (offset=30)
    assert allocs_two[1].offset == 30
