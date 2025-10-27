from __future__ import annotations

from typing import (
    Any,
    Literal,
    Generic,
    TypeVar,
    Annotated,
    TypedDict,
    TypeGuard,
    NotRequired,
    LiteralString,
)
from abc import abstractmethod, ABC
from functools import cached_property
from dataclasses import dataclass

T = TypeVar("T")

try:
    from pydantic import Discriminator

    _Discriminator = Discriminator
except ModuleNotFoundError | ImportError:
    _Discriminator = None

import enum


class SupportedStatement(str, enum.Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class Pathable(Generic[T]):
    _path: list[LiteralString]
    _inner: T

    def __init__(
        self, name: LiteralString, inner: T, /, old_p: Pathable | None = None
    ) -> None:
        if old_p is not None:
            self._path = old_p._path + [name]
        else:
            self._path = [name]
        self._inner = inner

    def get_str(self) -> LiteralString:
        return ".".join(self._path)


class Field:
    def __init__(
        self, name: LiteralString, /, prev: LiteralString | None = None
    ) -> None:
        self.name = name
        if prev is not None:
            self.path = prev + "." + name
        else:
            self.path = name


class Table(Field, enum.Enum):
    pass


class Schema(type[Table], enum.Enum):
    pass


class TestTable(Table):
    pk = Field("pk")
    id = Field("id")
    name_ = Field("name")
    salary = Field("salary")


class TestSchema(Schema):
    test_table = TestTable


t = TestSchema.test_table.id


def shit(f: Field):
    pass


@dataclass(frozen=True)
class Param:
    """A place holder for parameter."""

    class Config:
        param_str: LiteralString = "%s"

    name: LiteralString | None = None

    @cached_property
    def placeholder(self) -> LiteralString:
        """Get placeholder from name, e.g. "name" -> ":name"."""
        if self.name:
            return ":" + self.name
        else:
            return Param.Config.param_str


def is_param(o: Any) -> TypeGuard[Param]:
    """Check if an object is a parameter."""
    return isinstance(o, Param)


OPERATOR = (
    Literal[
        "IS",
        "IS NOT",
        "IN",
        "NOT IN",
        "LIKE",
        "NOT LIKE",
        "=",
        "!=",
        ">",
        "<",
        ">=",
        "<=",
    ]
    | LiteralString
)


class CONDITION(TypedDict):
    op: OPERATOR
    le: Param | EXPRESSION
    ri: Param | EXPRESSION


class LOGIC_OP_MULTI(TypedDict):
    logic: Literal["AND", "OR"]
    operands: list[EXPRESSION]


class LOGIC_OP_ONE(TypedDict):
    operands: EXPRESSION


LOGIC_OP = LOGIC_OP_ONE | LOGIC_OP_MULTI


class WHEN(TypedDict):
    cond: EXPRESSION
    then: EXPRESSION


_CASE_ELSE = TypedDict("_CASE_ELSE", {"else": NotRequired[LiteralString]})


class CASE(_CASE_ELSE):
    case: EXPRESSION
    whens: list[WHEN]


_ALIAS_AS = TypedDict("_ALIAS_AS", {"as": LiteralString})


class ALIAS(_ALIAS_AS):
    expr: LiteralString | Statement_SELECT


WHERE = LOGIC_OP | LiteralString


class WITH(TypedDict):
    with_query: list[ALIAS]
    recursive: NotRequired[bool]


FRAME_CLAUSE_MODE = Literal["RANGE", "ROWS", "GROUPS"]

FRAME_EXCLUSION = Literal["CURRENT ROW", "GROUP", "TIES", "NO OTHERS"]


class FRAME_END_OFFSET(TypedDict):
    offset: Param | LiteralString
    dir: Literal["PRECEDING", "FOLLOWING"]


FRAME_END = (
    Literal["UNBOUNDED PRECEDING", "CURRENT ROW", "UNBOUNDED FOLLOWING"]
    | FRAME_END_OFFSET
)


class FRAME_CLAUSE(TypedDict):
    mode: FRAME_CLAUSE_MODE
    start: FRAME_END
    end: NotRequired[FRAME_END]
    exclude: NotRequired[FRAME_EXCLUSION]


class _WINDOW(_ALIAS_AS):
    existing_window_name: NotRequired[LiteralString]
    partition_by: NotRequired[list[LiteralString]]
    order_by: NotRequired[list[ORDER_BY]]
    frame_clause: NotRequired[FRAME_CLAUSE]


WINDOW = _WINDOW | LiteralString


class OVER_CLAUSE(_ALIAS_AS):
    partition_by: NotRequired[list[LiteralString]]
    order_by: NotRequired[ORDER_BY]
    agg: LiteralString


SELECT_EXPRESSION = list[LiteralString | ALIAS | OVER_CLAUSE] | Literal["*"]


class SELECT_ALL(TypedDict):
    mode: Literal["ALL"]  # ALL is default
    expression: SELECT_EXPRESSION


class SELECT_DISTINCT(TypedDict):
    mode: Literal["DISTINCT"]
    expression: SELECT_EXPRESSION
    distinct_on: NotRequired[list[LiteralString]]


SELECT_TYPE = Annotated[SELECT_ALL | SELECT_DISTINCT, Discriminator("mode")]
SELECT = SELECT_TYPE | SELECT_EXPRESSION


class JOIN_CONDITION_ON(TypedDict):
    # type: Literal["ON"]
    on: CONDITION


class JOIN_CONDITION_USING(_ALIAS_AS):
    # type: Literal["USING"]
    using: list[LiteralString]


JOIN_CONDITION = JOIN_CONDITION_ON | JOIN_CONDITION_USING


class INNER_OUTER_JOIN(TypedDict):
    type: Literal["FULL", "LEFT", "RIGHT", "INNER"]
    cond: JOIN_CONDITION


class NATURAL_JOIN(TypedDict):
    type: Literal[
        "NATURAL FULL", "NATURAL LEFT", "NATURAL RIGHT", "NATURAL INNER"
    ]


class CROSS_JOIN(TypedDict):
    type: Literal["CROSS"]


JOIN = INNER_OUTER_JOIN | NATURAL_JOIN | CROSS_JOIN


class FROM_JOIN(TypedDict):
    expr: list[LiteralString | ALIAS]
    join: list[JOIN]


FROM = FROM_JOIN | LiteralString


class GROUP_BY(TypedDict):
    mode: NotRequired[Literal["ALL", "DISTINCT"]]  # None is default
    elems: list[LiteralString]  # TODO


SET_OPERATION_MODE = Literal["ALL", "DISTINCT"]


class SET_OPERATION(TypedDict):
    op: Literal["UNION", "INTERSECT", "EXCEPT"]
    mode: NotRequired[SET_OPERATION_MODE]  # distinct is default
    select: Statement_SELECT


class ORDER_BY(TypedDict):
    col: LiteralString
    order: NotRequired[Literal["ASC", "DESC"] | OPERATOR | LiteralString]
    nulls: NotRequired[Literal["FIRST", "LAST"]]


LIMIT = Param | LiteralString | Literal["ALL"]
OFFSET = Param | LiteralString


class FETCH_FIRST(TypedDict):
    first: Param | LiteralString
    with_ties: NotRequired[bool]


class FETCH_NEXT(TypedDict):
    next: Param | LiteralString
    with_ties: NotRequired[bool]


FETCH = FETCH_FIRST | FETCH_NEXT


class Statement_SELECT(TypedDict):
    type: Literal[SupportedStatement.SELECT]
    WITH: NotRequired[WITH]
    SELECT: SELECT
    FROM: NotRequired[FROM]
    WHERE: NotRequired[WHERE]
    GROUP_BY: NotRequired[GROUP_BY]
    HAVING: NotRequired[WHERE]
    WINDOW: NotRequired[list[WINDOW]]
    SET_OPERATIONS: NotRequired[list[SET_OPERATION]]
    ORDER_BY: NotRequired[list[ORDER_BY]]
    LIMIT: NotRequired[LIMIT]
    OFFSET: NotRequired[OFFSET]
    FETCH: NotRequired[FETCH]


class Statement_INSERT(TypedDict):
    type: Literal[SupportedStatement.INSERT]
    WITH: NotRequired[WITH]


class Statement_UPDATE(TypedDict):
    type: Literal[SupportedStatement.UPDATE]
    WITH: NotRequired[WITH]
    WHERE: NotRequired[CONDITION]


class Statement_DELETE(TypedDict):
    type: Literal[SupportedStatement.DELETE]
    WITH: NotRequired[WITH]
    WHERE: NotRequired[CONDITION]


EXPRESSION = LiteralString | CONDITION | CASE | Statement_SELECT

Statement = Annotated[
    Statement_SELECT | Statement_INSERT | Statement_UPDATE | Statement_DELETE,
    Discriminator("type"),
]


def construct_empty_select_statement() -> Statement_SELECT:
    return {
        "type": SupportedStatement.SELECT,
        "SELECT": "*",
    }
