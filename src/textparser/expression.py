from collections import defaultdict
from typing import Union, Dict, assert_never


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

    @property
    def is_scalar(self) -> bool:
        """Returns True if the expression has no symbolic terms (resolves to a pure integer)."""
        return len(self._terms) == 0

    def resolve_symbol(self, symbol: str, value: int) -> None:
        """
        Algebraically replaces a symbol with an integer value.
        Reduces the symbolic complexity of the expression by folding the value into the constant term.
        """
        if symbol in self._terms:
            coefficient = self._terms.pop(symbol)
            self._constant += coefficient * value

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
            case _:
                return NotImplemented

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
            case _:
                return NotImplemented

        return result._cleanup()

    def __rsub__(self, other) -> "Expression":
        # int - expr  OR  str - expr
        return Expression(other).__sub__(self)

    def __mul__(self, other: int) -> "Expression":
        # Supports scaling linear expressions (e.g. index * 4)
        match other:
            case int(x):
                result = Expression(self)
                result._constant *= x
                for sym in result._terms:
                    result._terms[sym] *= x
                return result._cleanup()
            case _:
                # We strictly disallow non-linear multiplication (Expr * Expr)
                return NotImplemented

    def __rmul__(self, other: int) -> "Expression":
        return self.__mul__(other)

    def _cleanup(self) -> "Expression":
        """Removes terms with zero coefficients (e.g. 'A - A')."""
        self._terms = {sym: coeff for sym, coeff in self._terms.items() if coeff != 0}
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
