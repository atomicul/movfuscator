from typing import List
from dataparser import Allocator, parse_data
from textparser import parse_cfg as parse_text_cfg, Function
from .symbols import resolve_symbols
from .expansion import expand_stack_ops
from .context import inject_context_switching


def preprocess_cfg(asm: str, allocator: Allocator, data_label: str) -> List[Function]:
    """
    Orchestrates the preprocessing pipeline:
    1. Parse Data & Text
    2. Resolve Symbols (Data Offsets)
    3. Expand Stack Operations (Push/Pop removal)
    4. Inject Context Switching (Register virtualization)
    """
    data_map = parse_data(allocator, asm)

    symbol_offsets = {
        name: allocations[0].offset
        for name, allocations in data_map.items()
        if allocations
    }

    functions = parse_text_cfg(asm)

    resolve_symbols(functions, symbol_offsets, data_label)

    expand_stack_ops(functions)

    inject_context_switching(functions, allocator, data_label)

    return functions
