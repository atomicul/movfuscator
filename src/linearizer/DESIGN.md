# Linearizer Implementation Plan

## Goal

Transform the CFG into a single loop where all blocks execute every iteration, but only the "active" block has side effects. This eliminates conditional jumps between blocks.

## Key Constraint

**cmov cannot write to memory** (`cmovcc %reg, mem` is invalid). We must use lookup-table-based pointer indirection instead.

## Approach: Lookup Table Indirection

For each memory write, redirect to either real memory or scratch based on whether the block is enabled:

```asm
# Load enabled flag (0 or 1) for this block
movl dispatch_var, %edi
movl block_K_enabled(,%edi,4), %edi

# Write through indirection
movl write_targets(,%edi,4), %esi   # targets[0]=scratch, targets[1]=real
movl %eax, (%esi)
```

## Memory Allocations

Per function with N blocks:
- `dispatch_var` (4 bytes): current block ID
- `scratch` (4 bytes): discard target for disabled writes
- `dispatch_write_targets` (8 bytes): `[&scratch, &dispatch_var]`
- `temp_enabled` (4 bytes): current block's enabled flag (0 or 1)
- `temp_write_reg` (4 bytes): save/restore for indirection register
- `temp_user_<reg>` (4 bytes each): save user register values during context save
- Per block K: `block_K_enabled[N]` (N×4 bytes): `enabled[K]=1`, others=0
- Per unique write destination: `write_targets` (8 bytes): `[&scratch, &real]`

## Linearized Code Structure

```asm
func_name:
    <prologue - save registers to real memory>
    movl $0, dispatch_var              # Start at entry block (ID 0)

func_name__loop:
    cmpl $-1, dispatch_var             # Exit sentinel
    je func_name__exit

    # Block 0
    movl dispatch_var, %edi
    movl block_0_enabled(,%edi,4), %edi
    movl %edi, temp_enabled            # Store enabled flag in memory
    <context load - always from real memory>
    <transformed instructions - writes use save/restore pattern>
    <context save with indirection - uses temp_user_* pattern>
    <dispatch update with indirection>

    # Block 1...N (same structure)
    ...

    jmp func_name__loop

func_name__exit:
    ret
```

## Instruction Transformations

### Block preamble (compute enabled flag once)
```asm
movl dispatch_var, %edi
movl block_K_enabled(,%edi,4), %edi
movl %edi, temp_enabled               # Store for use throughout block
```

### Simple memory write (with register save/restore)
```asm
# Before: movl %eax, __GLOBAL_MEM+36
# After:
movl %edi, temp_write_reg             # Save user's %edi
movl temp_enabled, %edi
movl var36_targets(,%edi,4), %edi
movl %eax, (%edi)
movl temp_write_reg, %edi             # Restore user's %edi
```

### Read-modify-write
```asm
# Before: addl $1, __GLOBAL_MEM+counter
# After:
movl __GLOBAL_MEM+counter, %eax       # Always read real value
addl $1, %eax
movl %edi, temp_write_reg             # Save user's %edi
movl temp_enabled, %edi
movl counter_targets(,%edi,4), %edi
movl %eax, (%edi)                     # Conditionally write
movl temp_write_reg, %edi             # Restore user's %edi
```

### Context save (epilogue) - special handling
```asm
# Before: movl %edi, __GLOBAL_MEM+edi_offset
# After:
movl %edi, temp_user_edi              # Save user's MODIFIED %edi value
movl temp_enabled, %edi               # Now safe to use %edi for indirection
movl edi_targets(,%edi,4), %edi
movl temp_user_edi, (%edi)            # Write user's value through indirection
# (no restore needed - block is ending)
```

### Dispatch update (DirectSuccessor)
```asm
# After context save, reload enabled flag
movl temp_enabled, %edi
movl dispatch_targets(,%edi,4), %edi
movl $NEXT_BLOCK_ID, (%edi)
```

### Dispatch update (ConditionalSuccessor)
```asm
# Condition already set FLAGS from cmp/test in block
# Use setcc + lookup (avoids cmov entirely)
set<cc> %cl                           # Get 0/1 from FLAGS
movzbl %cl, %ecx                      # Zero-extend to 32-bit
movl block_N_next(,%ecx,4), %eax      # next[0]=FALSE_ID, next[1]=TRUE_ID
movl temp_enabled, %edi               # Reload enabled flag
movl dispatch_targets(,%edi,4), %edi
movl %eax, (%edi)
```

### Exit (ret replacement)
```asm
movl temp_enabled, %edi
movl dispatch_targets(,%edi,4), %edi
movl $-1, (%edi)                      # Set exit sentinel
```

### Function calls
```asm
# Allocate once per function:
__noop_stub:
    ret

# Per call site - allocate: call_N_targets: .int __noop_stub, real_func
# Before: call printf
# After:
movl %edi, temp_write_reg             # Save user's %edi
movl temp_enabled, %edi
call *call_N_targets(,%edi,4)         # Indirect call through pointer table
movl temp_write_reg, %edi             # Restore user's %edi
```

Disabled blocks call `__noop_stub` (returns immediately), enabled blocks call the real function. Return values from no-op are garbage but discarded since context save goes to scratch.

## Files to Modify

### `src/linearizer/linearizer.py`
- Refactor `linearize_function()` to implement full linearization
- Add: `assign_block_ids()`, `collect_write_destinations()`, `allocate_tables()`
- Add: `transform_block()`, `transform_instruction()`, `emit_dispatch_update()`

### `src/linearizer/models.py`
- Keep existing `Function`, `Label`
- Add: `WriteTarget` dataclass (original_offset, table_offset)

### `src/linearizer/__init__.py`
- Update exports if needed

### `src/dataparser/models.py` and `src/dataparser/parser.py`
- Widen `Allocator.allocate_data` type from `List[Union[int, float]]` to `List[Union[int, float, str]]`
- Required for call target tables containing symbol references (e.g., `[__noop_stub, func]`)

### `src/memorymanager/allocation.py` and `src/memorymanager/manager.py`
- Widen `InputData` and `InternalValueType` to accept `str` in lists
- Matches the dataparser interface extension

## Register Usage

- `%edi`: used temporarily for indirection (saved/restored around each use)
- All registers remain available for user code
- Enabled flag stored in `temp_enabled` memory, not a register
- User register values preserved via save/restore pattern

## Implementation Steps

1. **Analysis phase**
   - Assign sequential IDs to blocks (entry=0)
   - Collect all unique memory write destinations

2. **Allocation phase**
   - Allocate dispatch_var, scratch, dispatch_write_targets
   - Allocate per-block enabled tables
   - Allocate per-destination write target tables

3. **Transformation phase**
   - For each block: emit enabled flag load, transform instructions, emit dispatch update
   - Handle DirectSuccessor vs ConditionalSuccessor dispatch logic

4. **Loop generation**
   - Wrap all blocks in loop with exit check
   - Emit function prologue and exit label

## Verification

1. Run `uvx ruff format src/` before commits
2. Run `uvx ruff check src/` for linting
3. Run `uv run pytest -v` for unit tests
4. Snapshot tests will update - review changes carefully
5. E2E tests must run on GitHub CI (not locally due to ARM architecture)
