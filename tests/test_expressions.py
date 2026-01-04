import pytest
from textparser import Expression


def test_init_values():
    """Test initialization with various types."""
    # Scalar (Int)
    e1 = Expression(10)
    assert e1.is_scalar
    assert str(e1) == "10"

    # Symbol (String)
    e2 = Expression("label")
    assert not e2.is_scalar
    assert str(e2) == "label"

    # Copy Constructor
    e3 = Expression(e2)
    assert str(e3) == "label"
    assert e3 is not e2  # Should be a new instance


def test_addition():
    """Test __add__ and __radd__ logic."""
    # Expr + Int
    e = Expression("A") + 5
    assert str(e) == "A+5"

    # Int + Expr
    e = 10 + Expression("A")
    assert str(e) == "A+10"

    # Expr + Str (Symbol)
    e = Expression(5) + "B"
    assert str(e) == "B+5"

    # Expr + Expr
    e = Expression("A") + Expression("B")
    assert str(e) == "A+B"


def test_subtraction():
    """Test __sub__ and __rsub__ logic."""
    # Expr - Int
    e = Expression("A") - 5
    assert str(e) == "A-5"

    # Int - Expr (10 - A -> -A + 10)
    e = 10 - Expression("A")
    assert str(e) == "-A+10"

    # Expr - Str
    e = Expression("A") - "B"
    # Output is sorted alphabetically: A - B
    assert str(e) == "A-B"

    # Self cancellation (A - A -> 0)
    e = Expression("A") - "A"
    assert e.is_scalar
    assert str(e) == "0"


def test_multiplication():
    """Test __mul__ and __rmul__ (scaling)."""
    # Expr * Int
    e = Expression("A") * 4
    assert str(e) == "4*A"

    # Int * Expr
    e = -1 * Expression("A")
    assert str(e) == "-A"

    # Zero multiplication
    e = Expression("A") * 0
    assert e.is_scalar
    assert str(e) == "0"


def test_complex_algebra():
    """Test mixing multiple operations and terms."""
    # 4 + A + 8 - A + B
    # Should resolve to: B + 12
    e = Expression(4) + "A" + 8 - "A" + "B"

    assert str(e) == "B+12"
    assert e.is_scalar is False

    e = (Expression("A") + 4) * 2 - Expression("A") * 3 + "B"
    assert str(e) == "-A+B+8"
    assert e.is_scalar is False


def test_substitute_term():
    """Test partial and full symbol resolution."""
    # Start: A + B + 10
    e = Expression("A") + "B" + 10

    # Resolve A -> 5
    # Result: 5 + B + 10 -> B + 15
    e.substitute_term("A", 5)

    assert str(e) == "B+15"
    assert not e.is_scalar

    # Resolve B -> 5
    # Result: 5 + 15 -> 20
    e.substitute_term("B", 5)

    assert str(e) == "20"
    assert e.is_scalar

    e2 = Expression("X") + Expression("Y") * 2

    # Substitute X -> (Z + 10)
    # Result: (Z + 10) + 2*Y -> 2*Y + Z + 10
    replacement = Expression("Z") + 10
    e2.substitute_term("X", replacement)

    assert str(e2) == "2*Y+Z+10"

    e3 = Expression("A") * 3

    # Substitute A -> (B - 2)
    # Result: 3 * (B - 2) -> 3*B - 6
    replacement_scaled = Expression("B") - 2
    e3.substitute_term("A", replacement_scaled)

    assert str(e3) == "3*B-6"

    # --- 4. Term Cancellation ---
    # Start: A + B
    e4 = Expression("A") + "B"

    # Substitute A -> -B (should result in 0)
    e4.substitute_term("A", Expression("B") * -1)

    assert str(e4) == "0"
    assert e4.is_scalar


def test_symbols_property():
    """Test the extraction of symbol names from an expression."""

    # 1. Scalar (No symbols)
    e = Expression(42)
    assert e.symbols == []

    # 2. Single Symbol
    e = Expression("start_label")
    assert e.symbols == ["start_label"]

    # 3. Multiple Symbols
    # Note: We sort to ensure deterministic comparison, as dict key order
    # is usually insertion-based but sets are safer for uniqueness checks.
    e = Expression("A") + "B"
    assert sorted(e.symbols) == ["A", "B"]

    # 4. Resolving symbols
    e.substitute_term("A", 5)
    assert e.symbols == ["B"]

    # 5. Symbols with coefficients
    e = Expression("X") * 4
    assert e.symbols == ["X"]

    # 6. Cancellation (Cleanup logic)
    # If a term is cancelled out (A - A), it should be removed from the symbols list
    e = Expression("A") + "B" - "A"
    assert e.symbols == ["B"]

    # 7. Parser integration check
    e = Expression.parse("base + index * 4")
    assert sorted(e.symbols) == ["base", "index"]


def test_cleanup_logic():
    """Ensure zero-coefficient terms are removed."""
    e = Expression("A")

    # Add B
    e = e + "B"
    # Remove B
    e = e - "B"

    # Internal terms dict should not contain 'B': 0
    # We verify this by checking the string output doesn't contain "0*B"
    assert str(e) == "A"


def test_formatting_edge_cases():
    """Test specific string formatting requirements for AT&T syntax."""
    # 1. Negative Constant
    e = Expression(-5)
    assert str(e) == "-5"

    # 2. Negative Symbol
    e = Expression("A") * -1
    assert str(e) == "-A"

    # 3. Symbol - Constant (should be A-5, not A+-5)
    e = Expression("A") - 5
    assert str(e) == "A-5"

    # 4. Sorting (A, B, C)
    e = Expression("C") + "A" + "B"
    assert str(e) == "A+B+C"

    # 5. Sorting with coefficients
    e = Expression("C") + Expression("A") * 2
    assert str(e) == "2*A+C"


def test_parse_scalars():
    """Test parsing of simple integer literals."""
    assert str(Expression.parse("0")) == "0"
    assert str(Expression.parse("42")) == "42"
    assert str(Expression.parse("-10")) == "-10"
    assert str(Expression.parse("+5")) == "5"


def test_parse_symbols():
    """Test parsing of variable names/symbols."""
    assert str(Expression.parse("x")) == "x"
    assert str(Expression.parse("my_var")) == "my_var"
    assert str(Expression.parse("VAR_123")) == "VAR_123"


def test_parse_basic_arithmetic():
    """Test basic addition, subtraction, and multiplication (scaling)."""
    # Addition
    assert str(Expression.parse("10 + 20")) == "30"
    assert str(Expression.parse("A + 5")) == "A+5"
    assert str(Expression.parse("5 + A")) == "A+5"

    # Subtraction
    assert str(Expression.parse("100 - 1")) == "99"
    assert str(Expression.parse("A - 5")) == "A-5"
    assert str(Expression.parse("10 - A")) == "-A+10"

    # Multiplication (Constant * Symbol)
    assert str(Expression.parse("2 * 4")) == "8"
    assert str(Expression.parse("3 * x")) == "3*x"
    assert str(Expression.parse("x * 3")) == "3*x"


def test_parse_precedence():
    """Verify that multiplication binds tighter than addition/subtraction."""
    # 1 + (2 * 3) = 7
    assert str(Expression.parse("1 + 2 * 3")) == "7"

    # (4 * 2) + 10 = 18
    assert str(Expression.parse("4 * 2 + 10")) == "18"

    # A + (2 * B)
    # Note: Expression.__str__ sorts terms alphabetically
    assert str(Expression.parse("A + 2 * B")) == "A+2*B"


def test_parse_parentheses():
    """Verify that parentheses override standard precedence."""
    # (1 + 2) * 3 = 9
    assert str(Expression.parse("(1 + 2) * 3")) == "9"

    # 2 * (A + 5) = 2A + 10
    assert str(Expression.parse("2 * (A + 5)")) == "2*A+10"

    # Nested parens: ((1+2)*3) + 4 = 13
    assert str(Expression.parse("((1 + 2) * 3) + 4")) == "13"


def test_parse_associativity():
    """Verify left-associativity for subtraction."""
    # 10 - 2 - 3  => (10 - 2) - 3 = 5
    # Should NOT be 10 - (2 - 3) = 11
    assert str(Expression.parse("10 - 2 - 3")) == "5"


def test_parse_unary_operators():
    """Test unary plus and minus."""
    assert str(Expression.parse("-A")) == "-A"
    assert str(Expression.parse("-(A + 1)")) == "-A-1"
    assert str(Expression.parse("+A")) == "A"

    # Double negative
    assert str(Expression.parse("-(-5)")) == "5"


def test_parse_parser_complex_algebra():
    """Test complex mixed expressions via the parser."""
    # 4 + A + 8 - A + B -> B + 12 (A cancels out)
    assert str(Expression.parse("4 + A + 8 - A + B")) == "B+12"

    # Distribution: 2*(A - 1) + 3*A -> 2A - 2 + 3A -> 5A - 2
    assert str(Expression.parse("2 * (A - 1) + 3 * A")) == "5*A-2"


def test_parse_whitespace_handling():
    """Test that whitespace is ignored."""
    assert str(Expression.parse("  A   +   B  ")) == "A+B"
    assert str(Expression.parse("\t1\n+\t2")) == "3"

    # Empty string logic (Source returns Expression(0) if no tokens)
    assert str(Expression.parse("")) == "0"
    assert str(Expression.parse("   ")) == "0"


def test_parse_errors():
    """Test invalid inputs and constraints."""

    # 1. Non-linear error (Multiplying two symbols)
    with pytest.raises(ValueError, match="Non-linear error"):
        Expression.parse("A * B")

    # 2. Invalid tokens (Remaining tokens)
    # Parser consumes "A", then halts at "%", then raises "Unexpected extra tokens"
    with pytest.raises(ValueError, match="Unexpected extra tokens"):
        Expression.parse("A % 2")

    # 3. Unbalanced parentheses (Missing closing)
    with pytest.raises(ValueError):
        Expression.parse("(A + 1")

    # 4. Unbalanced parentheses (Unexpected closing)
    with pytest.raises(ValueError, match="Unexpected extra tokens"):
        Expression.parse("A + 1)")

    # 5. Unexpected end of expression (Trailing operator)
    with pytest.raises(ValueError, match="Unexpected end"):
        Expression.parse("10 +")
