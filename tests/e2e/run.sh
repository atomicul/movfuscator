#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SAMPLES_DIR="$SCRIPT_DIR/samples"
TEMP_DIR=$(mktemp -d)

trap 'rm -rf "$TEMP_DIR"' EXIT

export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting End-to-End Tests...${NC}"
echo "Project Root: $PROJECT_ROOT"
echo "Temp Dir: $TEMP_DIR"
echo "----------------------------------------"

if ! command -v gcc &> /dev/null; then
    echo "Error: gcc is not installed."
    exit 2
fi

found_files=0
for src_file in "$SAMPLES_DIR"/*.s; do
    [ -e "$src_file" ] || continue
    found_files=1
    
    filename=$(basename -- "$src_file")
    name="${filename%.*}"
    
    echo -e "Testing ${YELLOW}$filename${NC}..."

    orig_bin="$TEMP_DIR/${name}_orig"
    obf_src="$TEMP_DIR/${name}_obf.s"
    obf_bin="$TEMP_DIR/${name}_obf"
    out_orig="$TEMP_DIR/${name}_orig.out"
    out_obf="$TEMP_DIR/${name}_obf.out"

    if ! gcc -m32 "$src_file" -o "$orig_bin"; then
        echo -e "${RED}[FAIL] Compilation of original source failed.${NC}"
        exit 2
    fi

    if ! "$orig_bin" > "$out_orig"; then
        echo -e "${RED}[FAIL] Original binary crashed or returned error code.${NC}"
        exit 2
    fi

    if ! python3 -m movfuscator "$src_file" -o "$obf_src"; then
        echo -e "${RED}[FAIL] Movfuscator failed to process file.${NC}"
        exit 1
    fi

    if ! gcc -m32 "$obf_src" -o "$obf_bin"; then
        echo -e "${RED}[FAIL] Compilation of obfuscated code failed.${NC}"
        exit 1
    fi

    if ! "$obf_bin" > "$out_obf"; then
        echo -e "${RED}[FAIL] Obfuscated binary crashed or returned error code.${NC}"
        exit 1
    fi

    if diff -q "$out_orig" "$out_obf" > /dev/null; then
        echo -e "${GREEN}[PASS] Outputs match.${NC}"
    else
        echo -e "${RED}[FAIL] Output mismatch!${NC}"
        echo "Original Output:"
        cat "$out_orig"
        echo "Obfuscated Output:"
        cat "$out_obf"
        exit 1
    fi
    echo "----------------------------------------"
done

if [ "$found_files" -eq 0 ]; then
    echo "No .s files found in $SAMPLES_DIR"
    exit 2
fi

echo -e "${GREEN}All tests passed successfully.${NC}"
