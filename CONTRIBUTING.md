# Contributing to Movfuscator

Thank you for your interest in contributing to the **Movfuscator** project!
This document explains the architecture, testing process, and roadmap for the
unimplemented features.

## 1. Architecture Overview

The dependencies are structured linearly, with no circular dependencies and in
a layered fashion, essentially forming a pipeline.

### System Diagram

```mermaid
flowchart TD
    Input[.s Assembly File]
    
    %% Components
    DataParser["Data Parser<br/>(src/dataparser)"]
    TextParser["Text Parser<br/>(src/textparser)"]
    MemoryManager["Memory Manager<br/>(src/memorymanager)"]
    SymbolResolver["Symbol Resolver<br/>(src/symbolsresolver)"]
    
    %% Flow
    Input --> DataParser
    Input --> TextParser
    
    %% Data Parser interactions
    DataParser -- "Allocates Variables" --> MemoryManager
    DataParser -- "Provides Offsets" --> SymbolResolver
    
    %% Text Parser interactions
    TextParser -- "Control Flow Graph" --> SymbolResolver
    
    %% Transformation Phase (Obfuscation Stubs)
    SymbolResolver --> Linearizer["Linearizer*<br/>(src/linearizer)"]
    Linearizer -- "Flat Instruction Stream" --> FlagExplicator["Flag Explicator*<br/>(src/flagexplicator)"]
    FlagExplicator --> InstReplacer["Instructions Replacer*<br/>(src/instructionreplacer)"]
    
    %% Side dependencies
    Linearizer -. "Uses" .-> MemoryManager
    FlagExplicator -. "Uses" .-> MemoryManager
    InstReplacer -. "Uses" .-> MemoryManager
    
    %% Final Assembly
    MemoryManager -- "Generates" --> DataSection[".data Section"]
    InstReplacer -- "Generates" --> TextSection[".text Section"]
    
    DataSection --> Output[.s Obfuscated File]
    TextSection --> Output

    %% Styling
    style Linearizer stroke:#f00,stroke-width:2px,stroke-dasharray: 5 5
    style FlagExplicator stroke:#f00,stroke-width:2px,stroke-dasharray: 5 5
    style InstReplacer stroke:#f00,stroke-width:2px,stroke-dasharray: 5 5
```

### Core Components

1.  **Memory Manager** (`src/memorymanager`): Helper class to allocate/initialize
memory into the .data section, used for both adding back existing variables and
internal use (e.g., scratch pads, lookup tables).
2.  **Data Parser** (`src/dataparser`): Parses `.data` section directives
(e.g., `.int`, `.asciz`) and registers them with the Memory Manager. Outputs a
dictionary of the parsed variables.
3.  **Text Parser** (`src/textparser`): Parses the `.text` section into a
Control Flow Graph (CFG). Encapsulates the assembly input into multiple useful
classes (`Function`, `Instruction`, `MemoryOperand`, `RegisterOperand`,
`ImmediateOperand`, `Expression`, etc.)
4.  **Symbol Resolver** (`src/symbolsresolver`): Combines the output of the two
parsers. It receives the variable map from the Data Parser and the CFG from the
Text Parser, replacing symbolic variable references with integer memory offsets
into the `.data` section.
5.  **Linearizer*** (`src/linearizer`): Responsible for flattening control flow.
Uses a single `jmp` instruction to loop through all code paths. Removes all
other jump instructions in favor of cmoves. Uses a state machine logic to decide
which block executes per cycle. Disables execution of all other blocks in that
cycle by using a pointer to irrelevant memory. (scratch pad)
6.  **Flag Explicator*** (`src/flagexplicator`): Responsible for movfuscating
the logic instructions that came off of the previous stage (`cmov`, `test`, `cmp`).
Instead of writing to EFLAGS, which cannot be read from with moves, we will write
to designated variables. We use those variables to implement the conditional
moves.
7.  **Instructions Replacer*** (`src/instructionreplacer`): Movfuscates the
remaining instructions. Converts more complex instructions into simpler instructions,
which are then converted into moves by using lookup tables.
8.  **Movfuscator CLI** (`src/movfuscator`): This is the code for serializing
the outputs of the whole pipeline. The code for the CLI interface also lies
within this package.

**❗Important**: Components marked with an asterisk (*) are not currently implemented.
They fulfil their minimum function to progress through the pipeline, but they
do not perform any obfuscation logic.

## 2. Testing

We use unit tests for modules only if it makes sense to do so. A lot of the
parsing logic is unit tested since it tends to be the most error-prone. Some
unit tests are snapshot tests. We also have end-to-end snapshot tests of the asm
files in the `tests/e2e/samples` directory. There is also a script
(`tests/e2e/run.sh`) to verify that the samples function identically before and
after movfuscation.

### Prerequisites
* **uv**: Used for dependency management and running the project.
* **GCC (32-bit)**: Required for compiling assembly samples during E2E tests.

### Running the CLI

```bash
uv run movfuscator --help
```

### Running Unit Tests
We use `pytest` with `syrupy` for snapshot testing to verify internal data
structures and parsing results.

```bash
uv run pytest -v
```

### Updating snapshots

```bash
uv run pytest --snaphsot-update
```

### Running E2E Tests
End-to-End tests ensure the obfuscated assembly functions identical to the
original. The script compiles the original code, compiles the obfuscated code,
runs both, and compares the output.

```bash
chmod +x tests/e2e/run.sh
uv run bash tests/e2e/run.sh
```

**Note**: The E2E script automatically looks for `.s` files in `tests/e2e/samples/`.

## 3. CI/CD
For all open PRs, there are automated checks for tests and other static analysis.
You should ensure the code is formatted with `uvx ruff format`, tests don't fail,
and `uvx ruff check` does not complain.
