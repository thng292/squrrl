from __future__ import annotations

from typing import LiteralString, overload


def _nl_join(l: list[LiteralString], indent: int):
    r"""Add new line (\\n) character bewteen strings."""
    indent_ = " " * indent
    return "\n".join(map(lambda it: indent_ + it, l))


@overload
def _add_indent(l: list[LiteralString], indent: int) -> map[LiteralString]: ...


@overload
def _add_indent(l: LiteralString, indent: int) -> LiteralString: ...


def _add_indent(l: list[LiteralString] | LiteralString, indent: int):
    indent_ = indent * " "
    if isinstance(l, list):

        def anon(it: LiteralString) -> LiteralString:
            return indent_ + it

        return map(anon, l)
    else:
        return indent_ + l


def _cat(
    *strs: LiteralString | None, delim: LiteralString = ", "
) -> LiteralString:
    a: filter[LiteralString] = filter(_is_not_none, strs)
    return delim.join(a)
