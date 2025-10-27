from . import core
from .select import SELECT, _WithContext

from copy import deepcopy
from typing import LiteralString


def wrap_str(s: LiteralString) -> LiteralString:
    """Wrap python string to sql string. E.g. a => 'a'."""
    return f"'{s}'"


_WithContext_ALL = _WithContext[core.Statement]


class _SELECT_able(_WithContext_ALL):
    def SELECT(self, s: core.SELECT):
        select_statement = core.construct_empty_select_statement()
        if "WITH" in self.statement:
            select_statement["WITH"] = self.statement["WITH"]
        return SELECT(select_statement, s)


class WITH(_SELECT_able, _WithContext_ALL):
    def __init__(
        self, building_statement: core.Statement, w: core.WITH
    ) -> None:
        self.statement = deepcopy(building_statement)
        self.statement["WITH"] = w


class _WITH_able(_WithContext):
    def WITH(self, w: core.WITH):
        return WITH(self.statement, w)


class SQLQuery(_SELECT_able, _WITH_able, _WithContext_ALL):
    """Starting point for bulding a query."""

    def __init__(self, statement: core.Statement | None = None) -> None:
        """Get a new query builder."""
        if statement is None:
            self.statement = core.construct_empty_select_statement()
        else:
            self.statement = statement


if __name__ == "__main__":
    print(
        SQLQuery()
        .WITH({"recursive": False, "with_query": []})
        .SELECT(
            [
                {"expr": "len(email)", "as": "email_len"},
                {
                    "expr": SQLQuery().SELECT("1").statement,
                    "as": "shit",
                },
                {
                    "as": "stuf",
                    "partition_by": "idk",
                    "order_by": {"col": "abc", "order": "ASC"},
                    "agg": "avg(col)",
                },
            ]
        )
        .WHERE(...)
        .GROUP_BY(...)
        .HAVING(...)
        .UNION(...)
        .UNION(...)
        .EXCEPT(...)
        .ORDER_BY(...)
        .LIMIT(...)
        .OFFSET(...)
        .construct_sql()
    )
    print(SQLQuery().SELECT(["email", "password"]).construct_sql())
