from __future__ import annotations

from typing import (
    Any,
    Literal,
    Protocol,
    runtime_checkable,
    TypeVar,
    Annotated,
    TypedDict,
    TypeGuard,
    NotRequired,
    LiteralString,
)
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


@runtime_checkable
class Pathable(Protocol):
    """A protocol for objects that can return their path string."""

    def get_str(self) -> LiteralString: ...


# ---------------------------------------------------------------------------
# 2. Implement the Field as a Descriptor
# ---------------------------------------------------------------------------
class Field(Pathable):
    """
    A descriptor representing a table field.

    Its __get__ method is triggered on class access (e.g., MyTable.my_field),
    allowing it to return a new Field instance with a path prefixed
    by the table's path.
    """

    def __init__(
        self, name: LiteralString, prev: LiteralString | None = None
    ) -> None:
        # The actual column name, e.g., "id", "name"
        self.field_name = name
        # The fully-qualified path, e.g., "tests.id"
        self._path = f"{prev}.{name}" if prev else name

    def get_str(self) -> LiteralString:
        """Returns the fully-qualified path of the field."""
        return self._path

    def __get__(self, obj: Any, objtype: type | None = None) -> "Field":
        """
        Called on class access (e.g., TestTable.id).
        `obj` is None, `objtype` is the class (TestTable).
        """
        if obj is None:
            # objtype is the class (e.g., TestTable).
            # We call its get_str() to get its path ("tests").
            table_path = objtype.get_str()
            # Return a *new* Field instance bound to this table path.
            return Field(self.field_name, prev=table_path)

        # Instance access (e.g., my_table_instance.id) is not supported here.
        raise AttributeError(
            "Field can only be accessed on the class, not an instance."
        )

    def _bind_prefix(self, prefix: LiteralString) -> "Field":
        """
        A helper used by TableWrapper to create a new Field
        with a schema-qualified path.
        """
        return Field(self.field_name, prev=prefix)


# ---------------------------------------------------------------------------
# 3. Implement the TableWrapper (for Schema-qualified Tables)
# ---------------------------------------------------------------------------
class TableWrapper(Pathable):
    """
    A proxy object that wraps a Table class when it's defined
    inside a Schema. It overrides the path and field access.
    """

    def __init__(self, path: LiteralString, original_table: Type["Table"]):
        self._path: LiteralString = path
        self._original_table = original_table

    def get_str(self) -> LiteralString:
        """Returns the schema-qualified table path (e.g., "TestSchema.tests")."""
        return self._path

    def __getattr__(self, name: str) -> Field:
        """
        Called on field access (e.g., TestSchema.test_table.id).
        'name' will be "id".
        """
        # Get the *original* Field descriptor from the *original* table
        original_field_descriptor = getattr(self._original_table, name)

        if isinstance(original_field_descriptor, Field):
            # Ask the original field to create a *new* copy of itself,
            # but bound to *this wrapper's* path.
            return original_field_descriptor._bind_prefix(self._path)

        raise AttributeError(f"'{self._path}' has no field '{name}'")


# ---------------------------------------------------------------------------
# 4. Implement Metaclasses for Table and Schema
# ---------------------------------------------------------------------------
class TableMeta(type):
    """
    Metaclass for Table. Intercepts class creation to:
    1. Determine the table's path (from Meta.table_name or class name).
    2. Store this path in `_path` on the class.
    3. Add a `get_str()` classmethod to the class.
    """

    def __new__(cls, name: str, bases: tuple, attrs: dict):
        # 1. Determine table path
        meta = attrs.get("Meta")
        table_name = getattr(meta, "table_name", None) or name.lower()

        # 2. Store path on the class
        attrs["_path"] = table_name

        # Create the new class (e.g., TestTable)
        new_class = super().__new__(cls, name, bases, attrs)

        # 3. Add get_str() classmethod
        def get_str(cls_or_self) -> LiteralString:
            return cls_or_self._path

        # Bind the method to the new class
        new_class.get_str = classmethod(get_str)

        return new_class


class SchemaMeta(type):
    """Metaclass for Schema. Intercepts class creation to.

    1. Determine the schema's path (from Meta.table_name or class name).
    2. Store this path in `_path`.
    3. Add a `get_str()` classmethod.
    4. Find all `Table` attributes and replace with `TableWrapper` instances.
    """

    def __new__(cls, name: str, bases: tuple, attrs: dict):
        # 1. Determine schema path
        meta = attrs.get("Meta")
        schema_name = getattr(meta, "table_name", None) or name

        # 2. Store path
        attrs["_path"] = schema_name

        # Create a copy to hold the new attributes (with wrappers)
        wrapped_attrs = attrs.copy()

        # 4. Find and replace Table attributes
        for attr_name, attr_value in attrs.items():
            # Check if it's a class AND a subclass of Table
            is_table_subclass = isinstance(attr_value, type) and any(
                issubclass(b, Table) for b in attr_value.__mro__ if b is Table
            )

            if is_table_subclass:
                # `attr_value` is the Table class (e.g., TestTable)
                # Get its base path (e.g., "tests")
                table_base_path = attr_value.get_str()

                # Create the new schema-qualified path
                wrapper_path = f"{schema_name}.{table_base_path}"

                # Create the wrapper and put it in the class attributes
                wrapper = TableWrapper(
                    path=wrapper_path, original_table=attr_value
                )
                wrapped_attrs[attr_name] = wrapper

        # Create the new class (e.g., TestSchema) using the *wrapped* attrs
        new_class = super().__new__(cls, name, bases, wrapped_attrs)

        # 3. Add get_str() classmethod
        def get_str(cls_or_self) -> LiteralString:
            return cls_or_self._path

        new_class.get_str = classmethod(get_str)

        return new_class


# ---------------------------------------------------------------------------
# 5. Define Base Classes using the Metaclasses
# ---------------------------------------------------------------------------
class Table(metaclass=TableMeta):
    # These are added by the metaclass, but defined here for type hinting
    _path: LiteralString

    @classmethod
    def get_str(cls) -> LiteralString: ...


class Schema(metaclass=SchemaMeta):
    # These are added by the metaclass, but defined here for type hinting
    _path: LiteralString

    @classmethod
    def get_str(cls) -> LiteralString: ...


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
