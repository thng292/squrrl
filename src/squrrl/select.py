from __future__ import annotations

from . import core
from .constructor import construct_sql_str

from copy import deepcopy
from typing import Generic, TypeVar, Protocol, LiteralString


T = TypeVar("T", bound=core.Statement)


class _WithContext(Protocol, Generic[T]):
    statement: T

    def construct_sql(self, indent: int | None = None) -> LiteralString:
        return construct_sql_str(self.statement, indent)


_WithContext_SELECT = _WithContext[core.Statement_SELECT]


class FETCH(_WithContext_SELECT):
    pass


class OFFSET(_WithContext_SELECT):
    def __init__(
        self, with_context: _WithContext_SELECT, offset: core.OFFSET
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        self.statement["OFFSET"] = offset


class _OFFSET_able(_WithContext_SELECT):
    def OFFSET(self, offset: int):
        return OFFSET(self, offset)


class LIMIT(_OFFSET_able, _WithContext_SELECT):
    def __init__(
        self, with_context: _WithContext_SELECT, limit: core.LIMIT
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        self.statement["LIMIT"] = limit


class _LIMIT_able(_WithContext_SELECT):
    def LIMIT(self, limit: core.LIMIT):
        return LIMIT(self, limit)


class ORDER_BY(
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self, with_context: _WithContext_SELECT, *order_by: core.ORDER_BY
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        # Code for support stacking ORDER BY, but it is not natural in sql
        # order_list = self.statement.get("ORDER_BY", [])
        # order_list.extend(order_by)
        # self.statement["ORDER_BY"] = order_list
        self.statement["ORDER_BY"] = list(order_by)


class _ORDER_BY_able(_WithContext_SELECT):
    def ORDER_BY(self, *order_by: core.ORDER_BY):
        return ORDER_BY(self, *order_by)


class _UNION_able(_WithContext_SELECT):
    def UNION(self, s: core.ALIAS, mode: core.SET_OPERATION_MODE = "DISTINCT"):
        return UNION(self, s, mode)

    def UNION_ALL(self, s: core.ALIAS):
        return UNION(self, s, "ALL")

    def UNION_DISTINCT(self, s: core.ALIAS):
        return UNION(self, s, "DISTINCT")


class _INTERSECT_able(_WithContext_SELECT):
    def INTERSECT(
        self, s: core.ALIAS, mode: core.SET_OPERATION_MODE = "DISTINCT"
    ):
        return INTERSECT(self, s, mode)

    def INTERSECT_ALL(self, s: core.ALIAS):
        return INTERSECT(self, s, "ALL")

    def INTERSECT_DISTINCT(self, s: core.ALIAS):
        return INTERSECT(self, s, "DISTINCT")


class _EXCEPT_able(_WithContext_SELECT):
    def EXCEPT(self, s: core.ALIAS, mode: core.SET_OPERATION_MODE = "DISTINCT"):
        return EXCEPT(self, s, mode)

    def EXCEPT_ALL(self, s: core.ALIAS):
        return EXCEPT(self, s, "ALL")

    def EXCEPT_DISTINCT(self, s: core.ALIAS):
        return EXCEPT(self, s, "DISTINCT")


class UNION(
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self,
        with_context: _WithContext_SELECT,
        s: core.ALIAS,
        mode: core.SET_OPERATION_MODE,
    ):
        self.statement = deepcopy(with_context.statement)
        set_ops = self.statement.get("SET_OPERATIONS", [])
        set_ops.append({"op": "UNION", "mode": mode, "select": s})
        self.statement["SET_OPERATIONS"] = set_ops


class INTERSECT(
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self,
        with_context: _WithContext_SELECT,
        s: core.ALIAS,
        mode: core.SET_OPERATION_MODE,
    ):
        self.statement = deepcopy(with_context.statement)
        set_ops = self.statement.get("SET_OPERATIONS", [])
        set_ops.append({"op": "UNION", "mode": mode, "select": s})
        self.statement["SET_OPERATIONS"] = set_ops


class EXCEPT(
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self,
        with_context: _WithContext_SELECT,
        s: core.ALIAS,
        mode: core.SET_OPERATION_MODE,
    ):
        self.statement = deepcopy(with_context.statement)
        set_ops = self.statement.get("SET_OPERATIONS", [])
        set_ops.append({"op": "UNION", "mode": mode, "select": s})
        self.statement["SET_OPERATIONS"] = set_ops


class WINDOW(
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self, with_context: _WithContext_SELECT, *windows: core.WINDOW
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        ws = self.statement.get("WINDOW", [])
        ws.extend(windows)
        self.statement["WINDOW"] = ws


class _WINDOW_able(_WithContext_SELECT):
    def WINDOW(self, *w: core.WINDOW):
        return WINDOW(self, *w)


class HAVING(
    _WINDOW_able,
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self, with_context: _WithContext_SELECT, condition: core.WHERE
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        self.statement["HAVING"] = condition


class _HAVING_able(_WithContext_SELECT):
    def HAVING(self, condition: core.WHERE):
        return HAVING(self, condition)


class GROUP_BY(
    _HAVING_able,
    _WINDOW_able,
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self, with_context: _WithContext_SELECT, g: core.GROUP_BY
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        self.statement["GROUP_BY"] = g


class _GROUP_BY_able(_WithContext_SELECT):
    def GROUP_BY(self, g: core.GROUP_BY):
        return GROUP_BY(self, g)


class WHERE(
    _GROUP_BY_able,
    _WINDOW_able,
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self, with_context: _WithContext_SELECT, condition: core.WHERE
    ) -> None:
        self.statement = deepcopy(with_context.statement)
        self.statement["WHERE"] = condition


class _WHERE_able(_WithContext_SELECT):
    def WHERE(self, condition: core.WHERE):
        return WHERE(self, condition)


class JOIN(_WithContext_SELECT):
    # TODO
    pass


class FROM(
    _WHERE_able,
    _GROUP_BY_able,
    _WINDOW_able,
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(self, with_context: _WithContext_SELECT, f: core.FROM) -> None:
        self.statement = deepcopy(with_context.statement)
        self.statement["FROM"] = f


class _FROM_able(_WithContext_SELECT):
    def FROM(self, f: core.FROM):
        return FROM(self, f)


class SELECT(
    _FROM_able,
    _WHERE_able,
    _GROUP_BY_able,
    _WINDOW_able,
    _UNION_able,
    _EXCEPT_able,
    _INTERSECT_able,
    _ORDER_BY_able,
    _LIMIT_able,
    _OFFSET_able,
    _WithContext_SELECT,
):
    def __init__(
        self, building_statement: core.Statement_SELECT, s: core.SELECT
    ) -> None:
        self.statement = deepcopy(building_statement)
        self.statement["SELECT"] = s
