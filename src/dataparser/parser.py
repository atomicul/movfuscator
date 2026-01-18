import re
import ast
from typing import Iterable, List, Union, Dict
from .models import Allocation, Allocator


def parse_data(
    data_allocator: Allocator, source_code: str
) -> Dict[str, List[Allocation]]:
    """
    Parses the .data section of assembly source code.
    Returns a dict mapping labels to their corresponding allocations.
    """
    labels: Dict[str, List[Allocation]] = {}
    current_label_name: str | None = None

    stream = source_code.splitlines()
    stream = strip_comments(stream)
    stream = filter_data_section(stream)

    for line in stream:
        if ":" in line:
            possible_label, remainder = line.split(":", 1)

            if re.match(r"^[a-zA-Z_.][a-zA-Z0-9_.]*$", possible_label.strip()):
                current_label_name = possible_label.strip()

                # Initialize the list for this label if it doesn't exist
                if current_label_name not in labels:
                    labels[current_label_name] = []

                line = remainder.strip()

            if not line:
                continue

        if current_label_name is None:
            current_label_name = "__anonymous_data"
            if current_label_name not in labels:
                labels[current_label_name] = []

        parts = line.split(maxsplit=1)
        directive = parts[0]
        args_str = parts[1].strip() if len(parts) > 1 else ""

        allocation = parse_directive(
            data_allocator, directive, args_str, current_label_name
        )

        if allocation:
            labels[current_label_name].append(allocation)

    return labels


def parse_directive(
    allocator: Allocator, directive: str, args_str: str, label_name: str
):
    """Parses specific directives and calls the allocator."""

    if directive in [".int", ".long"]:
        # TYPE FIX: Explicitly annotate as List[Union[int, float]]
        # Use int(x, 0) to auto-detect base (e.g. 0x123 vs 123)
        int_values: List[Union[int, float]] = [
            int(x.strip(), 0) for x in args_str.split(",") if x.strip()
        ]

        if not int_values:
            return None

        if len(int_values) == 1:
            return allocator.allocate_data(int_values[0], name=label_name)

        return allocator.allocate_data(int_values, name=label_name)

    elif directive == ".float":
        # TYPE FIX: Same annotation here for floats
        float_values: List[Union[int, float]] = [
            float(x.strip()) for x in args_str.split(",") if x.strip()
        ]

        if not float_values:
            return None

        val = float_values[0] if len(float_values) == 1 else float_values
        return allocator.allocate_data(val, name=label_name)

    elif directive in [".asciz", ".string", ".ascii"]:
        match = re.search(r'(".*")', args_str)
        if match:
            quoted_str = match.group(1)
            content = ast.literal_eval(quoted_str)

            return allocator.allocate_data(content, name=label_name)

    elif directive in [".zero", ".space", ".skip"]:
        try:
            size = int(args_str.split()[0], 0)
            return allocator.allocate_empty(size, name=label_name)
        except (ValueError, IndexError):
            return None

    return None


def strip_comments(stream: Iterable[str]) -> Iterable[str]:
    for line in stream:
        line = line.split("#", 1)[0]
        line = line.split("//", 1)[0]
        line = line.strip()

        if line:
            yield line


def filter_data_section(stream: Iterable[str]) -> Iterable[str]:
    in_data = False
    for line in stream:
        if line.startswith(".section .data") or line == ".data":
            in_data = True
            continue

        elif line.startswith(".section") or line in [".text", ".bss"]:
            in_data = False
            continue

        if in_data:
            yield line
