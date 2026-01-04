import re
from collections import defaultdict
from typing import Optional, List, Union, Dict, assert_never


class Expression:
    """
    Represents a generic linear expression: Constant + (k1*Sym1) + (k2*Sym2)...

    This class models the algebraic structure of the expression only. It is agnostic
    as to whether the value represents an absolute memory address, a relative offset,
    or an immediate value.

    Usage:
        - To model an absolute address: Expression("Label")
        - To model an offset: Expression("Field") + 4
        - To rebase an offset into a section: Expression(offset) + "DATA_START"
    """

    def __init__(self, value: Union[int, str, "Expression"] = 0):
        # The constant integer component of the expression (C)
        self._constant: int = 0
        # The map of symbolic terms: { "symbol_name": coefficient }
        self._terms: Dict[str, int] = defaultdict(int)

        match value:
            case int(x):
                self._constant = x
            case str(x):
                # A raw string is treated as 1 * Symbol
                self._terms[x] = 1
            case Expression() as x:
                self._constant = x._constant
                self._terms = x._terms.copy()
            case x:
                assert_never(x)

    @staticmethod
    def parse(text: str) -> "Expression":
        """
        Parses a string representation of a linear expression (e.g., "A + 2*B - 5").
        Supports: Integers, Symbols, +, -, *, and Parentheses.
        """

        tokens: List[str] = [
            t for t in re.split(r"([+*\-()])|\s+", text) if t and t.strip()
        ]
        cursor = 0

        def peek() -> Optional[str]:
            return tokens[cursor] if cursor < len(tokens) else None

        def consume(expected: Optional[str] = None) -> Optional[str]:
            nonlocal cursor
            token = peek()
            if expected and token != expected:
                raise ValueError(
                    f"Expected '{expected}', got '{token}' at position {cursor}"
                )
            cursor += 1
            return token

        def parse_expr() -> "Expression":
            # Expr -> Term { (+|-) Term }
            node = parse_term()
            while peek() in ("+", "-"):
                op = consume()
                rhs = parse_term()
                if op == "+":
                    node = node + rhs
                else:
                    node = node - rhs
            return node

        def parse_term() -> "Expression":
            # Term -> Factor { * Factor }
            node = parse_factor()
            while peek() == "*":
                consume()
                rhs = parse_factor()

                match (node, rhs):
                    case (Expression(), Expression()):
                        raise ValueError(
                            "Non-linear error: Cannot multiply two symbols."
                        )
                    case Expression() as x, y:
                        node = x * y
                    case x, y:
                        node = x * y

            return Expression(node)

        def parse_factor() -> Union["Expression", int]:
            # Factor -> ( Expr ) | - Factor | + Factor | Integer | Symbol
            token = peek()
            if token is None:
                raise ValueError("Unexpected end of expression")

            if token == "(":
                consume()
                e = parse_expr()
                consume(")")
                return e
            elif token == "-":
                consume()
                return Expression(0) - parse_factor()  # Unary minus
            elif token == "+":
                consume()
                return parse_factor()  # Unary plus
            elif token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
                consume()
                return int(token)
            elif re.match(r"^[a-zA-Z_.][a-zA-Z0-9_.]*$", token):
                consume()
                return Expression(token)
            else:
                raise ValueError(f"Unexpected token: {token}")

        if not tokens:
            return Expression(0)

        result = parse_expr()
        if cursor < len(tokens):
            raise ValueError(f"Unexpected extra tokens: {tokens[cursor:]}")
        return result

    @property
    def is_scalar(self) -> bool:
        """Returns True if the expression has no symbolic terms (resolves to a pure integer)."""
        return len(self._terms) == 0

    @property
    def symbols(self):
        return list(self._terms.keys())

    def substitute_term(self, term: str, value: Union[int, "Expression"]):
        """
        Replaces a symbol in the expression with an integer or another Expression.
        Modifies the expression in-place.

        Args:
            term: The symbol name to replace.
            value: The replacement (int or Expression).
        """
        if term not in self._terms:
            return

        coefficient = self._terms.pop(term)

        match value:
            case int(v):
                self._constant += v * coefficient

            case Expression() as v:
                self._constant += v._constant * coefficient

                for sub_term, sub_coeff in v._terms.items():
                    self._terms[sub_term] += sub_coeff * coefficient

            case x:
                assert_never(x)

        self._cleanup()

    def __add__(self, other: Union["Expression", str, int]) -> "Expression":
        result = Expression(self)

        match other:
            case int(x):
                result._constant += x
            case str(x):
                result._terms[x] += 1
            case Expression() as x:
                result._constant += x._constant
                for sym, coeff in x._terms.items():
                    result._terms[sym] += coeff
            case x:
                assert_never(x)

        return result._cleanup()

    def __radd__(self, other) -> "Expression":
        return self.__add__(other)

    def __sub__(self, other: Union["Expression", str, int]) -> "Expression":
        result = Expression(self)

        match other:
            case int(x):
                result._constant -= x
            case str(x):
                result._terms[x] -= 1
            case Expression() as x:
                result._constant -= x._constant
                for sym, coeff in x._terms.items():
                    result._terms[sym] -= coeff
            case x:
                assert_never(x)

        return result._cleanup()

    def __rsub__(self, other) -> "Expression":
        # int - expr  OR  str - expr
        return Expression(other).__sub__(self)

    def __mul__(self, other: int) -> "Expression":
        # Supports scaling linear expressions (e.g. index * 4)
        result = Expression(self)
        result._constant *= other
        for sym in result._terms:
            result._terms[sym] *= other
        return result._cleanup()

    def __rmul__(self, other: int) -> "Expression":
        return self.__mul__(other)

    def _cleanup(self) -> "Expression":
        """Removes terms with zero coefficients (e.g. 'A - A')."""
        cleaned = {sym: coeff for sym, coeff in self._terms.items() if coeff != 0}
        self._terms = defaultdict(int, cleaned)
        return self

    def __str__(self) -> str:
        """
        Emits standard AT&T/GAS syntax suitable for re-injection.
        """
        if self.is_scalar:
            return str(self._constant)

        parts = []

        # Sort terms for deterministic output
        for sym, coeff in sorted(self._terms.items()):
            if coeff == 1:
                parts.append(sym)
            elif coeff == -1:
                parts.append(f"-{sym}")
            else:
                parts.append(f"{coeff}*{sym}")

        # Append the constant term if it exists
        if self._constant > 0:
            parts.append(f"{self._constant}")
        elif self._constant < 0:
            parts.append(f"{self._constant}")

        # Join and clean up syntax (e.g., "A+-5" -> "A-5")
        res = "+".join(parts).replace("+-", "-")

        return res if res else "0"

    def __repr__(self):
        return f"Expr(constant={self._constant}, terms={dict(self._terms)})"
