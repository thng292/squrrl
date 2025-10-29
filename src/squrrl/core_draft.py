from __future__ import annotations

from . import utils

from typing import (
    Any,
    Literal,
    TypeVar,
    Protocol,
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


class SqlPart(Protocol):
    def get_parts(self, indent: int) -> list[LiteralString]: ...


class Column(SqlPart):
    """A descriptor representing a table column.

    It auto-infer its name from
    the class attribute it's assigned to.
    """

    name: LiteralString | None
    schema_name: LiteralString | None
    table_name: LiteralString | None

    def __init__(
        self,
        name: LiteralString | None = None,  # <-- Name is now optional
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
        # Store prev so __set_name__ can use it later
        self.schema_name = schema_name
        self.table_name = table_name

    def get_parts(self, indent: int) -> list[LiteralString]:
        return [self.get_path()]

    def __set_name__(self, owner: type[Any], name: LiteralString) -> None:
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
                "Ensure it is assigned as a class attribute."
            )
        return utils._cat(
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
            table_path = objtype.get_path()
            return Column(self.name, table_name=table_path)

        # Instance access (e.g., my_table_instance.id) is not supported here.
        raise AttributeError(
            "Field can only be accessed on the class, not an instance."
        )

    def _bind_prefix(
        self, table_name: LiteralString, schema_name: LiteralString | None
    ) -> Column:
        """Used by TableWrapper to create new Column with schema path."""
        if self.name is None:
            raise AttributeError(
                "Canot bind an unnamed Field.\n"
                "Field has no name. Was it assigned to a class attribute?"
            )
        return Column(self.name, table_name, schema_name)

    def AS(self, name: LiteralString) -> ALIAS:
        return ALIAS(name, self)


class TableMeta(type):
    """Metaclass for Table. Intercepts class creation to.

    1. Determine the table's path (from Meta.table_name or class name).
    2. Store this path in `_path` on the class.
    """

    def __new__(cls, name: str, bases: tuple, attrs: dict):
        meta = attrs.get("Meta")
        table_name = str(getattr(meta, "table_name", None) or name.lower())
        attrs["_table_name"] = table_name
        attrs["_schema_name"] = None
        new_class = super().__new__(cls, name, bases, attrs)
        return new_class

    def __getattr__(cls: type[Table], name: str) -> Column:
        """Called on field access (e.g., TestSchema.test_table.id).

        'name' will be "id".
        """
        # Get the *original* Field descriptor from the n*original* table
        original_field_descriptor = getattr(cls._original_table, name)

        if isinstance(original_field_descriptor, Column):
            # Ask the original field to create a *new* copy of itself,
            # but bound to *this wrapper's* path.
            return original_field_descriptor._bind_prefix(
                cls._table_name, cls._schema_name
            )

        raise AttributeError(f"'{cls._path}' has no field '{name}'")


class Table(metaclass=TableMeta):
    _schema_name: LiteralString | None
    _table_name: LiteralString

    @classmethod
    def get_path(cls) -> LiteralString:
        return utils._cat(cls._schema_name, cls._table_name, delim=".")

    @classmethod
    def JOIN(cls: type[Table], other: type[Table]) -> type[Table]:
        class Shit(cls): ...

        return cls

    @classmethod
    def get_parts(cls, indent: int) -> list[LiteralString]: ...


class SchemaMeta(type):
    """Metaclass for Schema. Intercepts class creation to.

    1. Determine the schema's path (from Meta.schema_name or class name).
    2. Store this path in `_path`.
    4. Find all `Table` attributes and replace with `TableWrapper` instances.
    """

    def __new__(cls, name: str, bases: tuple, attrs: dict):
        # 1. Determine schema path
        meta = attrs.get("Meta")
        schema_name = getattr(meta, "schema_name", None) or name

        # 2. Store path
        attrs["_schema_name"] = schema_name

        # Create a copy to hold the new attributes (with wrappers)
        wrapped_attrs = attrs.copy()

        # 4. Find and replace Table attributes
        for attr_name, attr_value in attrs.items():
            # Check if it's a class AND a subclass of Table
            if isinstance(attr_value, type) and issubclass(attr_value, Table):
                original_table: type[Table] = attr_value

                # Get the original table's base path (e.g., "tests")
                table_base_path = original_table.get_path()

                new_path = f"{schema_name}.{table_base_path}"
                # Preserve Meta class and other stuff
                new_dict = original_table.__dict__.copy()
                new_dict["_schema_name"] = new_path

                # Create a new class inherited from the user defined class
                proxy_class = type(
                    f"{name}_{original_table.__name__}",
                    (original_table,),
                    new_dict,
                )

                # Replace the attribute on the schema with the new class
                wrapped_attrs[attr_name] = proxy_class

        # Create the new class (e.g., TestSchema) using the *wrapped* attrs
        new_class = super().__new__(cls, name, bases, wrapped_attrs)

        return new_class


class Schema(metaclass=SchemaMeta):
    # These are added by the metaclass, but defined here for type hinting
    _schema_name: LiteralString

    @classmethod
    def get_path(cls) -> LiteralString:
        return cls._schema_name


@dataclass(frozen=True)
class Param:
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


class ALIAS(SqlPart):
    expr: LiteralString | Column | type[Table] | None
    alias: LiteralString

    def __init__(self, name: LiteralString, column: Column) -> None:
        super().__init__(column.name, column._prev)
        self.alias = name

    def get_path(self) -> LiteralString:
        return super().get_path()

    def get_parts(self, indent: int) -> list[LiteralString]:
        res = super().get_parts(indent)
        if len(res) == 1:
            return [f"({res[0]}) AS f{self.alias}"]
        else:
            res = utils._add_indent(res, indent)
            return ["(", *res, f") AS {self.alias}"]


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

EXPRESSION = LiteralString


class Condition(SqlPart):
    class Prev(TypedDict):
        cond: Condition
        op: Literal["AND", "OR"]

    le: Param | EXPRESSION
    op: OPERATOR
    ri: Param | EXPRESSION
    _prev: Prev | None

    def __init__(
        self,
        le: Param | EXPRESSION,
        op: OPERATOR,
        ri: Param | EXPRESSION,
        neg: bool = False,
    ) -> None:
        self.le = le
        self.op = op
        self.ri = ri

        self.neg = neg
        self._prev = None

    @staticmethod
    def NOT(
        le: Param | EXPRESSION, op: OPERATOR, ri: Param | EXPRESSION
    ) -> Condition:
        return Condition(le, op, ri, True)

    def AND(
        self, le: Param | EXPRESSION, op: OPERATOR, ri: Param | EXPRESSION
    ) -> Condition:
        res = Condition(le, op, ri)
        res._prev = {"cond": self, "op": "AND"}
        return res

    def OR(
        self, le: Param | EXPRESSION, op: OPERATOR, ri: Param | EXPRESSION
    ) -> Condition:
        res = Condition(le, op, ri)
        res._prev = {"cond": self, "op": "OR"}
        return res

    def get_parts(self, indent: int) -> list[LiteralString]: ...


class FROM:
    class JoinState(TypedDict):
        type: LiteralString
        natural: bool
        table: type[Table]

    table: type[Table]
    joins: JoinState | None

    def NATURAL(self): ...

    def CROSS_JOIN(self): ...

    def JOIN(self): ...

    def LEFT(self): ...


class SELECT:
    def __init__(self, *cols: Column) -> None:
        pass

    def FROM(self, *tables: type[Table]): ...


class WITH:
    def SELECT(self, *cols: Column): ...


class SqlBuilder:
    def WITH(self, *args): ...
    def SELECT(self, *cols: Column): ...


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


if __name__ == "__main__":
    pass
