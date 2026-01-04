import argparse
import sys
from pathlib import Path
from . import movfuscate


def main():
    parser = argparse.ArgumentParser(
        description="Movfuscator: Linearize x86 assembly control flow into a single dispatch loop."
    )
    parser.add_argument(
        "input_file", type=Path, help="Path to the input assembly file (.s)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to the output file. If omitted, prints to stdout.",
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        source_code = args.input_file.read_text()
        linearized_asm = movfuscate(source_code)

        if args.output:
            args.output.write_text(linearized_asm)
            print(f"Linearized assembly written to: {args.output}", file=sys.stderr)
        else:
            print(linearized_asm)

    except Exception as e:
        print(f"Error processing file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
