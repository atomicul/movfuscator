from typing import assert_never
from memorymanager import MemoryManager
import instructionreplacer
from instructionreplacer import Label, Instruction


def movfuscate(source_code: str) -> str:
    """
    Takes raw assembly, parses it, flattens the CFG of EACH function individually,
    and returns linearized assembly code.
    """
    data_label = "__GLOBAL_MEM"
    memory_manager = MemoryManager()

    movfuscated_functions = instructionreplacer.movfuscate(
        source_code, memory_manager, data_label
    )

    return (
        generate_data_section(memory_manager, data_label)
        + "\n"
        + generate_text_section(movfuscated_functions)
    )


def generate_data_section(memory_manager: MemoryManager, data_label: str) -> str:
    """Generates the assembly lines for the .data section."""
    lines = [".section .data", f"{data_label}:"]

    for alloc in memory_manager.allocations:
        lines.append(f"    {alloc}")

    return "\n".join(lines) + "\n"


def generate_text_section(linearized_functions: list) -> str:
    """Generates the assembly lines for the .text section."""
    lines = [".section .text"]

    for func in linearized_functions:
        lines.append("")
        lines.append(f".global {func.name}")

        # If the first instruction is a label but not the function name itself,
        # we ensure it gets printed.
        first_item = func.instructions[0]
        if isinstance(first_item, Label) and first_item != func.name:
            lines.append(f"{first_item}:")

        for item in func.instructions:
            match item:
                case Label() as label:
                    lines.append(f"{label}:")
                case Instruction() as instruction:
                    lines.append(f"    {instruction}")
                case x:
                    assert_never(x)

    return "\n".join(lines) + "\n"
