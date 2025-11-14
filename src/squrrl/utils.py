from __future__ import annotations

from typing import Iterable, TypeGuard, LiteralString, overload


def nl_join(l: list[LiteralString], indent: int):
    r"""Add new line (\\n) character bewteen strings."""
    indent_ = " " * indent
    return "\n".join(map(lambda it: indent_ + it, l))


@overload
def add_indent(
    l: Iterable[LiteralString], indent: int
) -> map[LiteralString]: ...


@overload
def add_indent(l: LiteralString, indent: int) -> LiteralString: ...


def add_indent(l: Iterable[LiteralString] | LiteralString, indent: int):
    indent_ = indent * " "
    if isinstance(l, str):
        return indent_ + l
    else:

        def anon(it: LiteralString) -> LiteralString:
            return indent_ + it

        return map(anon, l)


def is_not_none(a: LiteralString | None) -> TypeGuard[LiteralString]:
    return a is not None and bool(a)


def cat(
    *strs: LiteralString | None, delim: LiteralString = ", "
) -> LiteralString:
    a: filter[LiteralString] = filter(is_not_none, strs)
    return delim.join(a)
