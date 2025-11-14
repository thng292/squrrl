from __future__ import annotations

from . import utils

from abc import ABC, abstractmethod
from typing import (
    Any,
    Literal,
    TypeVar,
    ClassVar,
    Protocol,
    Annotated,
    TypeAlias,
    TypedDict,
    TypeGuard,
    NotRequired,
    LiteralString,
    final,
    overload,
)
from functools import cached_property
from dataclasses import dataclass

from typing_extensions import override


T = TypeVar("T")

try:
    from pydantic import Discriminator

    _Discriminator = Discriminator
except ModuleNotFoundError | ImportError:
    _Discriminator = None

import enum


################################################################################
# START OF STANDARD DEFINITIONS (SCHEMA, TABLE, COLUMN, PARAM)
################################################################################


class SupportedStatement(str, enum.Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


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


class Statement_DELETE(TypedDict):
    type: Literal[SupportedStatement.DELETE]
    WITH: NotRequired[WITH]


Statement = (
    Statement_SELECT | Statement_INSERT | Statement_UPDATE | Statement_DELETE
)


class _HasStateSelect(ABC):
    statement: Statement_SELECT

    def get_sql(self, indent: int | None = None) -> LiteralString:
        indent_ = indent or 0
        res: list[LiteralString] = []
        order = [
            "WITH",
            "SELECT",
            "FROM",
            "WHERE",
            "GROUP_BY",
            "WINDOW",
            "SET_OPERATIONS",
            "ORDER_BY",
            "LIMIT",
            "OFFSET",
            "FETCH",
        ]

        for part in order:
            if part not in self.statement:
                continue

            tmp = self.statement[part].get_sql_parts(indent_)
            if isinstance(tmp, str):
                res.append(tmp)
            else:
                res.extend(tmp)

        if indent is None:
            return " ".join(res)
        return "\n".join(res)


class _SQLPart(ABC):
    """Base class of all SQL parts has get_sql_parts method."""

    @abstractmethod
    def get_sql_parts(
        self, indent: int
    ) -> LiteralString | list[LiteralString]: ...


class ColumnDerivable(_SQLPart, ABC):
    """Shits that **may** result in 1 row and 1 column."""

    pass


class TableDerivable(ColumnDerivable, ABC):
    """Shits that **may** result in a table."""

    pass


@dataclass(frozen=True)
class Param(ColumnDerivable):
    """A place holder for parameter."""

    class Config:
        """Config for parameter."""

        param_str: LiteralString = "%s"

    name: LiteralString | None = None

    @cached_property
    def placeholder(self) -> LiteralString:
        """Get placeholder from name, e.g. "name" -> ":name"."""
        if self.name:
            return ":" + self.name
        else:
            return Param.Config.param_str

    def get_sql_parts(self, indent: int) -> LiteralString:
        return f":{self.name}" if self.name else self.Config.param_str


class Column(ColumnDerivable):
    """A descriptor representing a table column.

    It auto-infer its name from
    the class attribute it's assigned to.
    """

    name: LiteralString | None
    schema_name: LiteralString | None
    table_name: LiteralString | None

    def __init__(
        self,
        name: LiteralString | None = None,
        table_name: LiteralString | None = None,
        schema_name: LiteralString | None = None,
    ) -> None:
        """Represent a column in the database.

        If name is not set, it will be infered from the class'field name. e.g.
        ```
        class Table:
            pk = Column()  # <-- name will be "pk"
        ```
        """
        self.name = name
        self.schema_name = schema_name
        self.table_name = table_name

    def get_sql_parts(self, indent: int) -> LiteralString:
        return self.get_path()

    def __set_name__(
        self, owner: type[NoAs_Table], name: LiteralString
    ) -> None:
        """Called when the Field is assigned to a class attribute.

        `owner` is the class (e.g., EmployeesTable).
        `name` is the attribute name (e.g., "pk").
        """
        # If the user didn't provide a name in __init__ (it's None)...
        if self.name is None:
            self.name = name

    def get_path(self) -> LiteralString:
        """Returns the fully-qualified path of the field."""
        if self.name is None:
            # name was None and __set_name__ never ran
            raise AttributeError(
                "Field was not properly initialized. "
                + "Ensure it is assigned as a class attribute."
            )
        return utils.cat(
            self.schema_name, self.table_name, self.name, delim="."
        )

    def __get__(self, obj: Any, objtype: type | None = None) -> Column:
        """Called on class access (e.g., TestTable.id).

        `obj` is None, `objtype` is the class (TestTable).
        """
        if obj is None and objtype is not None and issubclass(objtype, Table):
            if self.name is None:
                raise AttributeError(
                    "Field has no name. Was it assigned to a class attribute?"
                )
            table_path = objtype.get_sql_parts(0)
            return Column(self.name, table_name=table_path)

        # Instance access (e.g., my_table_instance.id) is not supported here.
        raise AttributeError(
            "Field can only be accessed on the class, not an instance."
        )

    def AS(self, name: LiteralString) -> ColumnAlias:
        return ColumnAlias(name, self)


class ColumnAlias(ColumnDerivable):
    def __init__(self, name: LiteralString, col: Column) -> None:
        self.alias: LiteralString = name
        self.col: Column = col

    def get_sql_parts(self, indent: int) -> LiteralString:
        return f"{self.col.get_sql_parts(indent)} AS {self.alias}"


class TableMeta(type):
    """Metaclass for Table. Intercepts class creation to.

    1. Determine the table's path (from Meta.table_name or class name).
    2. Store this path in `_path` on the class.
    """

    def __new__(cls, name: str, bases: tuple[type], attrs: dict[str, Any]):
        if "_table_name" not in attrs:
            attrs["_table_name"] = name.lower()
        assert isinstance(attrs["_table_name"], str), (
            "_table_name must be string"
        )

        if "_schema_name" not in attrs:
            attrs["_schema_name"] = None

        new_class = super().__new__(cls, name, bases, attrs)
        return new_class


class Table(metaclass=TableMeta):
    _schema_name: ClassVar[LiteralString | None] = None
    _table_name: ClassVar[LiteralString]

    ALL: ClassVar[Column] = Column("*")

    @classmethod
    def get_sql_parts(cls, indent: int) -> LiteralString:
        return utils.cat(cls._schema_name, cls._table_name, delim=".")

    @classmethod
    def JOIN(cls: type[Table], other: type[Table]) -> TableDerivable:
        return cls

    @classmethod
    def AS(cls, alias: LiteralString) -> TableDerivable:
        pass


class SchemaMeta(type):
    """Metaclass for Schema. Intercepts class creation to.

    1. Determine the schema's path (from Meta.schema_name or class name).
    2. Store this path in `_path`.
    4. Find all `Table` attributes and replace with `TableWrapper` instances.
    """

    def __new__(cls, name: str, bases: tuple[type], attrs: dict[str, Any]):
        if "_schema_name" not in attrs:
            attrs["_schema_name"] = name.lower()
        assert isinstance(attrs["_schema_name"], str), (
            "_schema_name must be string"
        )
        schema_name = attrs["_schema_name"]

        wrapped_attrs = attrs.copy()

        # Find and replace Table attributes
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, type) and issubclass(attr_value, Table):
                # attr_value._schema_name = schema_name
                original_table: type[Table] = attr_value
                tmp = attr_value.__dict__.copy()
                tmp["_schema_name"] = schema_name

                proxy_class = type(
                    f"{name}_{original_table.__name__}",
                    (original_table,),
                    tmp,
                )

                wrapped_attrs[attr_name] = proxy_class

        # Create the new class (e.g., TestSchema) using the *wrapped* attrs
        new_class = super().__new__(cls, name, bases, wrapped_attrs)

        return new_class


class Schema(metaclass=SchemaMeta):
    _schema_name: ClassVar[LiteralString]

    @classmethod
    def get_sql_parts(cls) -> LiteralString:
        return cls.get_path()

    @classmethod
    def get_path(cls) -> LiteralString:
        return cls._schema_name


################################################################################
# START OF SELECT QUERY
################################################################################


# class ALIAS:
#     expr: LiteralString | Column | type[Table] | None
#     alias: LiteralString

#     def __init__(self, name: LiteralString, column: Column) -> None:
#         super().__init__(column.name, column._prev)
#         self.alias = name

#     def get_path(self) -> LiteralString:
#         return super().get_path()

#     def get_parts(self, indent: int) -> list[LiteralString]:
#         res = super().get_parts(indent)
#         if len(res) == 1:
#             return [f"({res[0]}) AS f{self.alias}"]
#         else:
#             res = utils._add_indent(res, indent)
#             return ["(", *res, f") AS {self.alias}"]


class GROUP_BY(_SQLPart, _HasStateSelect):
    def __init__(self) -> None:
        super().__init__()

    @override
    def get_sql_parts(self, indent: int) -> LiteralString | list[LiteralString]:
        return ""


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
        "AND",
        "OR",
    ]
    | LiteralString
)


@final
class Criterion(_SQLPart):
    """Represents a condition or a chain of conditions in a WHERE clause."""

    class Prev(TypedDict):
        op: OPERATOR
        cr: Criterion

    _prev: Prev
    le: Expression
    op: OPERATOR
    ri: Param | Expression
    neg: bool

    def __init__(
        self,
        le: Expression,
        op: OPERATOR,
        ri: Expression,
        neg: bool = False,
    ) -> None:
        """Initializes a condition.

        Args:
            le: Left-hand side of the expression.
            op: Operator.
            ri: Right-hand side of the expression.
            neg: Whether the condition is negated.
        """
        self.le = le
        self.op = op
        self.ri = ri

        self.neg = neg

    @staticmethod
    def NOT(le: Expression, op: OPERATOR, ri: Expression) -> Criterion:
        """Creates a negated condition."""
        return Criterion(le, op, ri, True)

    def AND(self, criterion: Criterion):
        criterion._prev = {"op": "AND", "cr": self}
        return criterion

    def OR(self, criterion: Criterion):
        criterion._prev = {"op": "OR", "cr": self}
        return criterion

    @staticmethod
    def _get_sql_part_helper(
        part: Expression, indent: int
    ) -> LiteralString | list[LiteralString]:
        sql_parts = (
            part if isinstance(part, str) else part.get_sql_parts(indent)
        )
        if isinstance(sql_parts, list):
            res: list[LiteralString] = ["("]
            res.extend(utils.add_indent(sql_parts, indent))
            res.append(")")
            return res
        else:
            if isinstance(part, Criterion):
                return f"({sql_parts})"
            return sql_parts

    @override
    def get_sql_parts(self, indent: int) -> LiteralString | list[LiteralString]:
        """Gets the SQL parts for this condition."""
        le = self._get_sql_part_helper(self.le, indent)
        ri = self._get_sql_part_helper(self.ri, indent)

        if isinstance(le, str) and isinstance(ri, str):
            # Single line
            return f"{le} {self.op} {ri}"

        res: list[LiteralString] = []
        if isinstance(le, list):
            res.extend(le)
        else:
            res.append(le)

        res[-1] += f" {self.op} "

        if isinstance(ri, list):
            res.extend(ri)
        else:
            res[-1] += ri

        if self.neg:
            res[0] = "NOT " + res[0]

        if self._prev is not None:
            prev = self._prev["cr"].get_sql_parts(indent)
            res[0] = self._prev["op"] + " " + res[0]
            if isinstance(prev, list):
                res = prev + res
            else:
                res.insert(0, prev)
        return res


Expression = Criterion | ColumnDerivable | LiteralString

SET_QUANTIFIER = Literal["ALL", "DISTINCT"]


@final
class WHERE(_SQLPart, _HasStateSelect):
    def __init__(
        self, statement: Statement_SELECT, condition: Criterion
    ) -> None:
        self.statement = statement
        self.statement["WHERE"] = self
        self.condition = condition

    @override
    def get_sql_parts(self, indent: int) -> LiteralString | list[LiteralString]:
        tmp = self.condition.get_sql_parts(indent)
        res: list[LiteralString] = ["WHERE"]
        if isinstance(tmp, list):
            res.extend(utils.add_indent(tmp, indent))
        else:
            res.append(tmp)
        return res


class _WHERE_able(_HasStateSelect):
    def WHERE(self, condition: Criterion):
        return WHERE(self.statement, condition)


@final
class FROM(_WHERE_able, TableDerivable, _HasStateSelect):
    FromArg = type[Table] | TableDerivable

    def __init__(self, statement: Statement_SELECT, table: FromArg) -> None:
        self.statement = statement
        self.statement["FROM"] = self
        self.table = table

    @override
    def get_sql_parts(self, indent: int) -> LiteralString | list[LiteralString]:
        indent_ = indent * " "
        table = self.table.get_sql_parts(indent)
        res: list[LiteralString] = ["FROM"]
        if isinstance(table, str):
            res.append(indent_ + table)
        else:
            res.extend(utils.add_indent(table, indent))

        return res


class _FROM_able(_HasStateSelect):
    def FROM(self: _HasStateSelect, table: FROM.FromArg):
        return FROM(self.statement, table)


@final
class SELECT(_FROM_able, _WHERE_able, ColumnDerivable, _HasStateSelect):
    ColArg = ColumnDerivable | Literal["*"] | LiteralString

    def __init__(
        self,
        with_clause: WITH | None,
        select_mode: SET_QUANTIFIER,
        *cols: SELECT.ColArg,
    ) -> None:
        self.cols = list(cols)
        self.select_mode = select_mode
        self.statement = {"type": SupportedStatement.SELECT, "SELECT": self}
        if with_clause is not None:
            self.statement["WITH"] = with_clause

    @override
    def get_sql_parts(self, indent: int) -> list[LiteralString]:
        indent_ = " " * indent

        res: list[LiteralString] = []
        res.append("SELECT" if self.select_mode == "ALL" else "SELECT DISTINCT")
        for i, col in enumerate(self.cols):
            if isinstance(col, str):
                res.append(indent_ + col)
            else:
                tmp = col.get_sql_parts(indent)
                if isinstance(tmp, str):
                    res.append(indent_ + tmp)
                else:
                    res.extend(utils.add_indent(tmp, indent))
            if i < len(self.cols) - 1:
                res[-1] += ","
        return res


class WITH(TableDerivable):
    def __init__(
        self, table: TableDerivable | type[Table], alias: LiteralString
    ) -> None:
        self.table: TableDerivable | type[Table] = table
        self.alias: LiteralString = alias

    def SELECT(self, *cols: SELECT.ColArg):
        return SELECT(self, "ALL", *cols)

    def SELECT_DISTINCT(self, *cols: SELECT.ColArg):
        return SELECT(self, "DISTINCT", *cols)

    @override
    def get_sql_parts(self, indent: int) -> LiteralString | list[LiteralString]:
        tmp = self.table.get_sql_parts(indent)
        if isinstance(tmp, LiteralString):
            return f"{tmp} AS  {self.alias}"
        else:
            return ["(", *utils.add_indent(tmp, indent), f") AS {self.alias}"]


class SqlBuilder:
    @classmethod
    def WITH(cls, table: type[Table] | TableDerivable, alias: LiteralString):
        return WITH(table, alias)

    @classmethod
    def SELECT(cls, *cols: SELECT.ColArg):
        return SELECT(None, "ALL", *cols)

    @classmethod
    def SELECT_DISTINCT(cls, *cols: SELECT.ColArg):
        return SELECT(None, "DISTINCT", *cols)


if __name__ == "__main__":
    pass
