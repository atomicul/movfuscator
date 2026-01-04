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

test_files=("$SAMPLES_DIR"/*.s)
declare -a test_statuses

passed_count=0
failed_count=0

for (( i=0; i<${#test_files[@]}; i++ )); do
    src_file="${test_files[$i]}"
    [ -f "$src_file" ] || continue
    
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
        test_statuses[$i]=2
        ((failed_count++))
        echo "----------------------------------------"
        continue
    fi

    if ! "$orig_bin" > "$out_orig"; then
        echo -e "${RED}[FAIL] Original binary crashed or returned error code.${NC}"
        test_statuses[$i]=2
        ((failed_count++))
        echo "----------------------------------------"
        continue
    fi

    if ! python3 -m movfuscator "$src_file" -o "$obf_src"; then
        echo -e "${RED}[FAIL] Movfuscator failed to process file.${NC}"
        test_statuses[$i]=1
        ((failed_count++))
        echo "----------------------------------------"
        continue
    fi

    if ! gcc -m32 "$obf_src" -o "$obf_bin"; then
        echo -e "${RED}[FAIL] Compilation of obfuscated code failed.${NC}"
        test_statuses[$i]=1
        ((failed_count++))
        echo "----------------------------------------"
        continue
    fi

    if ! "$obf_bin" > "$out_obf"; then
        echo -e "${RED}[FAIL] Obfuscated binary crashed or returned error code.${NC}"
        test_statuses[$i]=1
        ((failed_count++))
        echo "----------------------------------------"
        continue
    fi

    if diff -q "$out_orig" "$out_obf" > /dev/null; then
        echo -e "${GREEN}[PASS] Outputs match.${NC}"
        test_statuses[$i]=0
        ((passed_count++))
    else
        echo -e "${RED}[FAIL] Output mismatch!${NC}"
        echo "Original Output:"
        cat "$out_orig"
        echo "Obfuscated Output:"
        cat "$out_obf"
        test_statuses[$i]=1
        ((failed_count++))
    fi
    echo "----------------------------------------"
done

if [ "${#test_files[@]}" -eq 0 ]; then
    echo "No .s files found in $SAMPLES_DIR"
    exit 2
fi

worst_status=$(printf "%s\n" "${test_statuses[@]}" | sort -n | tail -1)
total_tests=$((passed_count + failed_count))

echo ""
echo "========================================"
echo -e "              TEST SUMMARY              "
echo "========================================"
echo "Total Tests:  $total_tests"
echo -e "Passed:       ${GREEN}$passed_count${NC}"
echo -e "Failed:       ${RED}$failed_count${NC}"
echo "========================================"
echo ""

if [[ "$worst_status" -eq 0 ]]; then
    echo -e "${GREEN}All tests passed successfully.${NC}"
else
    echo -e "${RED}Some tests failed.${NC}"
fi

exit "$worst_status"
