from enum import Enum
from typing import Any, LiteralString


class TableColumn:
    def __init__(self, schema_name, table_name, column_name):
        self._schema_name = schema_name
        self._table_name = table_name
        self._column_name = column_name
        self._path = f"{schema_name}.{table_name}.{column_name}"

    def __str__(self):
        return self._path

    def __repr__(self):
        return f'"{self._path}"'


class Table(TableColumn, Enum):
    def __init__(self, schema_name, table_name):
        self._schema_name = schema_name
        self._table_name = table_name
        self._path = f"{schema_name}.{table_name}"

    def __getattr__(self, item):
        return TableColumn(self._schema_name, self._table_name, item)

    def __str__(self):
        return self._path

    def __repr__(self):
        return f'"{self._path}"'


class Schema:
    def __init__(self):
        for attr in dir(self):
            if (
                not attr.startswith("_")
                and isinstance(getattr(self, attr), type)
                and issubclass(getattr(self, attr), Table)
            ):
                setattr(self, attr, Table(self.__class__.__name__, attr))


class Test(Table):
    pass


class TestSchema(Schema):
    Test = Test


schema = TestSchema()
print(str(schema.Test.value))  # "TestSchema.Test.pk"
print(str(schema.Test))  # "TestSchema.Test"
