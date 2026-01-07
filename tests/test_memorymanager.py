import pytest
from memorymanager import MemoryManager


def test_allocate_basic_types():
    """Verifies allocation logic for supported primitive types."""
    mm = MemoryManager()

    # 1. Integer (4 bytes)
    alloc_int = mm.allocate_data(42, "var_int")
    assert alloc_int.offset == 0
    assert alloc_int.size == 4

    # 2. Float (4 bytes)
    alloc_float = mm.allocate_data(3.14, "var_float")
    assert alloc_float.offset == 4
    assert alloc_float.size == 4

    # 3. String (Length + 1 null terminator)
    # "Hello" = 5 chars + 1 null = 6 bytes
    alloc_str = mm.allocate_data("Hello", "var_str")
    assert alloc_str.offset == 8
    assert alloc_str.size == 6


def test_allocate_lists():
    """Verifies allocation for homogeneous lists."""
    mm = MemoryManager()

    # List of ints: 3 items * 4 bytes = 12 bytes
    alloc_list = mm.allocate_data([10, 20, 30], "var_list")

    assert alloc_list.offset == 0
    assert alloc_list.size == 12


def test_allocate_empty():
    """Verifies reservation of empty memory blocks."""
    mm = MemoryManager()

    alloc_buf = mm.allocate_empty(1024, "buffer")

    assert alloc_buf.offset == 0
    assert alloc_buf.size == 1024


def test_automatic_alignment_padding():
    """
    Verifies that the manager inserts hidden padding to maintain alignment.
    Default alignment is 4 bytes.
    """
    mm = MemoryManager(alignment=4)

    # 1. Allocate a string of 3 bytes ("Hi" + null)
    # Occupies offsets 0, 1, 2. Next free byte is 3.
    mm.allocate_data("Hi", "short_str")

    # 2. Allocate an int (requires 4-byte alignment)
    # Manager should insert 1 byte of padding at offset 3.
    # New allocation should start at offset 4.
    alloc_int = mm.allocate_data(100, "aligned_int")

    assert alloc_int.offset == 4

    # Check that the internal offset tracker accounts for the padding
    # 4 (offset) + 4 (size) = 8
    assert mm._current_offset == 8


def test_invalid_inputs():
    """Verifies error handling for unsupported types or values."""
    mm = MemoryManager()

    # Empty list
    with pytest.raises(ValueError, match="Cannot allocate empty list"):
        mm.allocate_data([], "empty_list")

    # Invalid size
    with pytest.raises(ValueError, match="Size must be positive"):
        mm.allocate_empty(-10, "bad_size")


def test_data_section_snapshot(snapshot):
    """
    Snapshot test to verify the exact assembly output.
    Constructs a memory layout with mixed types and padding.
    """
    mm = MemoryManager(master_label="GLOBAL_MEM", alignment=4)

    # 1. Standard Int
    mm.allocate_data(1337, "counter")

    # 2. String causing misalignment
    # "A" + null = 2 bytes. Ends at offset 6.
    mm.allocate_data("A", "flag")

    # 3. Next Int (Should trigger 2 bytes of padding to reach offset 8)
    mm.allocate_data(99, "next_val")

    # 4. Empty Buffer
    mm.allocate_empty(16, "scratch_pad")

    # 5. List of Floats
    mm.allocate_data([1.1, 2.2, 3.3], "coefficients")

    generated_asm = mm.generate_data_section()

    print(generated_asm)

    assert generated_asm == snapshot
