from __future__ import annotations

from . import core

from typing import (
    Any,
    Literal,
    TypeVar,
    TypeGuard,
    LiteralString,
    overload,
)


T = TypeVar("T")


def _check(pred: Any, res: T) -> T | None:
    if bool(pred):
        return res
    return None


def _is_not_none(a: LiteralString | None) -> TypeGuard[LiteralString]:
    return a is not None and bool(a)


def _cat(
    *strs: LiteralString | None, delim: LiteralString = ", "
) -> LiteralString:
    a: filter[LiteralString] = filter(_is_not_none, strs)
    return delim.join(a)


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


def _get_placeholder(a: core.Param | T) -> LiteralString | T:
    if core.is_param(a):
        return a.placeholder
    return a


def _construct_with_clause(w: core.WITH, indent: int) -> list[LiteralString]:
    parts: list[LiteralString] = [
        "WITH RECURSIVE" if w.get("recursive", False) else "WITH"
    ]
    for query in w["with_query"]:
        if len(parts) != 1:
            parts[-1] += ","
        parts.append(f"{query['as']} AS (")
        if isinstance(query["expr"], str):
            parts[-1] += query["expr"] + ")"
        else:
            select_statement = construct_select_statement(
                query["expr"], indent=indent, return_parts=True
            )
            parts.extend(_add_indent(select_statement, indent))
            parts.append(")")
    return parts


def _construct_alias(a: core.ALIAS, indent: int) -> list[LiteralString]:
    if isinstance(a["expr"], str):
        return [f"{a['expr']} AS {a['as']}"]
    expr = construct_select_statement(
        a["expr"], indent=indent, return_parts=True
    )
    parts: list[LiteralString] = ["("]
    parts.extend(_add_indent(expr, indent))
    parts.append(f") AS {a['as']}")
    return parts


def _construct_order_by(orders: list[core.ORDER_BY]) -> LiteralString:
    parts: list[LiteralString] = []
    for it in orders:
        order = it.get("order")
        if order:
            if order == "ASC" or order == "DESC":
                _order_ = order
            else:
                _order_ = f"USING {order}"
        else:
            _order_ = None
        nulls = it.get("nulls")
        parts.append(_cat(it["col"], nulls and f"NULLS {nulls}", _order_))

    return "ORDER BY " + ", ".join(parts)


def _construct_order_limit_offset_fetch(
    s: core.Statement_SELECT,
) -> list[LiteralString]:
    parts: list[LiteralString] = []
    order = s.get("ORDER_BY")
    if order:
        parts.append(_construct_order_by(order))
    limit = s.get("LIMIT")
    if limit:
        parts.append(f"LIMIT {_get_placeholder(limit)}")  # type: ignore
    offset = s.get("OFFSET")
    if offset:
        parts.append(f"OFFSET {_get_placeholder(offset)}")  # type: ignore
    fetch = s.get("FETCH")
    if fetch:
        if "first" in fetch:
            type = "FIRST"
            num = fetch["first"]
        else:
            type = "NEXT"
            num = fetch["next"]
        parts.append(f"FETCH {type} {_get_placeholder(num)} ROWS")  # type: ignore
    return parts


def _construct_frame_end(end: core.FRAME_END) -> LiteralString:
    if isinstance(end, str):
        return end
    return f"{_get_placeholder(end['offset'])} {end['dir']}"  # type: ignore


def _construct_frame(frame: core.FRAME_CLAUSE) -> LiteralString:
    end = frame.get("end")
    start_ = _construct_frame_end(frame["start"])

    if end:
        end_ = _construct_frame_end(end)
    else:
        end_ = None
    exclusion = frame.get("exclude")
    return _cat(
        frame["mode"],
        end and "BETWEEN",
        start_,
        end and "AND",
        end_,
        exclusion,
    )


def _construct_windows(windows: list[core.WINDOW]) -> list[LiteralString]:
    parts: list[LiteralString] = ["WINDOW"]
    for window in windows:
        if isinstance(window, str):
            parts.append(window)
            continue
        partition = window.get("partition_by")
        order = window.get("order_by")
        if frame := window.get("frame_clause"):
            frame_ = _construct_frame(frame)
        else:
            frame_ = None

        parts.append(
            _cat(
                window["as"],
                "AS (",
                window.get("existing_window_name"),
                "PARTITION BY" if partition else None,
                ", ".join(partition) if partition else None,
                _construct_order_by(order) if order else None,
                frame_,
                ")",
            )
        )

    return parts


def _construct_condition(c: core.CONDITION, indent: int) -> list[LiteralString]:
    parts = []

    def anon(side: Literal["le", "ri"]):
        tmp = c[side]
        if core.is_param(tmp):
            parts.append()
        else:
            e = _construct_expression(tmp, indent)

    anon("le")
    parts.append(c["op"])
    anon("ri")

    return parts


def _construct_expression(
    e: core.EXPRESSION, indent: int
) -> list[LiteralString]:
    if isinstance(e, str):
        return [e]
    if "type" in e:
        return construct_select_statement(e, indent=indent, return_parts=True)
    elif "case" in e:
        return _construct_case(e, indent)
    else:
        return _construct_condition(e)

    pass


def _construct_case(case_: core.CASE, indent: int) -> list[LiteralString]:
    parts: list[LiteralString] = [
        f"CASE {_construct_select_expr(case_['case'], indent)}"
    ]
    parts.append("END")
    return parts


def _construct_logic_op(
    logic: core.LOGIC_OP, indent: int
) -> list[LiteralString]:
    for operand in logic["operands"]:
        pass


def _construct_having(having: core.WHERE, indent: int) -> list[LiteralString]:
    if isinstance(having, str):
        return [f"HAVING {having}"]
    else:
        return []


def _construct_select_expr(
    s: core.SELECT_EXPRESSION, indent: int
) -> list[LiteralString]:
    if isinstance(s, str):
        return [s]
    parts: list[LiteralString] = []
    for it in s:
        if isinstance(it, str):
            parts.append(it)
            continue
        if "expr" in it:
            if isinstance(it["expr"], str):
                constructing = it["expr"]
            else:
                constructing = construct_select_statement(it["expr"])
        else:
            constructing = f"{it['agg']} OVER"
            if "partition_by" in it:
                constructing += f" (PARTITION BY {it['partition_by']})"
            if "order_by" in it:
                constructing += (
                    f" (PARTITION BY {_construct_order_by([it['order_by']])})"
                )

        constructing += f" AS {it['as']}"
        parts.append(constructing)
    return parts


def _construct_select_clause(
    s: core.SELECT, indent: int
) -> list[LiteralString]:
    parts: list[LiteralString] = ["SELECT"]
    if isinstance(s, str):
        parts.append(s)
    elif isinstance(s, list):
        parts.append(_nl_join(_construct_select_expr(s, indent), indent))
    else:
        if s["mode"] == "DISTINCT":
            parts[0] += " DISTINCT"
            distinct_on = s.get("distinct_on")
            if distinct_on:
                if isinstance(distinct_on, list):
                    tmp = ", ".join(distinct_on)
                else:
                    tmp = distinct_on
                parts.append(f"ON ({tmp})")
        parts.append(
            _nl_join(_construct_select_expr(s["expression"], indent), indent)
        )
    return parts


@overload
def construct_select_statement(
    statement: core.Statement_SELECT,
    *,
    indent: int | None = None,
    return_parts: Literal[False],
) -> LiteralString: ...


@overload
def construct_select_statement(
    statement: core.Statement_SELECT,
    *,
    return_parts: Literal[True],
    indent: int | None = None,
) -> list[LiteralString]: ...


@overload
def construct_select_statement(
    statement: core.Statement_SELECT,
    *,
    indent: int | None = None,
) -> LiteralString: ...


def construct_select_statement(
    statement: core.Statement_SELECT,
    *,
    return_parts: bool = False,
    indent: int | None = None,
) -> LiteralString | list[LiteralString]:
    indent = indent or 0
    parts: list[LiteralString] = []
    params = ()
    with_clause = statement.get("WITH")
    if with_clause:
        w_c = _construct_with_clause(with_clause, indent)

        parts.append(_nl_join(w_c, indent))
    return parts if return_parts else "\n".join(parts)


def construct_sql_str(
    statement: core.Statement, indent: int | None = None
) -> LiteralString:
    match statement["type"]:
        case core.SupportedStatement.SELECT:
            return construct_select_statement(statement, indent=indent)
    return " "
