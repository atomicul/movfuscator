from typing import List
from linearizer import get_linearized_asm, Allocator, Function


def movfuscate(asm: str, allocator: Allocator, data_label: str) -> List[Function]:
    return get_linearized_asm(asm, allocator, data_label)
