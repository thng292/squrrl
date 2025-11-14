from . import core_draft as core

import unittest


class EmployeesTable(core.Table):
    _table_name = "employees"

    user_defined_stuff = 10

    pk = core.Column()
    id = core.Column()
    name = core.Column()
    salary = core.Column()
    dept = core.Column()


class Dept_Info(core.Table):
    user_defined_stuff = 11

    pk = core.Column()
    id = core.Column()
    dept = core.Column()
    desc = core.Column()


class CompanySchema(core.Schema):
    _schema_name = "company"

    user_defined_stuff = 10

    employees = EmployeesTable
    deptinfo = Dept_Info


class TestPath(unittest.TestCase):
    def test_path(self):
        def shit(a: type[core.Table]):
            pass
            # print(a.get_sql_parts())

        # print(type(CompanySchema))
        # print(CompanySchema.employees)
        # print(CompanySchema.employees.user_defined_stuff)
        shit(CompanySchema.employees)  # Type hint check

        self.assertEqual(Dept_Info.get_sql_parts(0), "dept_info")
        self.assertEqual(Dept_Info.ALL.get_sql_parts(0), "dept_info.*")
        self.assertEqual(Dept_Info.desc.get_sql_parts(0), "dept_info.desc")
        self.assertEqual(EmployeesTable.get_sql_parts(0), "employees")
        self.assertEqual(EmployeesTable.ALL.get_sql_parts(0), "employees.*")
        self.assertEqual(EmployeesTable.id.get_sql_parts(0), "employees.id")
        self.assertEqual(
            CompanySchema.employees.get_sql_parts(0), "company.employees"
        )
        self.assertEqual(
            CompanySchema.employees.ALL.get_sql_parts(0), "company.employees.*"
        )
        self.assertEqual(
            CompanySchema.employees.id.get_sql_parts(0), "company.employees.id"
        )
        self.assertEqual(
            CompanySchema.deptinfo.get_sql_parts(0), "company.dept_info"
        )
        self.assertEqual(
            CompanySchema.deptinfo.dept.get_sql_parts(0),
            "company.dept_info.dept",
        )


class TestSelect(unittest.TestCase):
    def test_0(self):
        res = core.SqlBuilder.SELECT(CompanySchema.employees.ALL).get_sql_parts(
            2
        )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0], "SELECT")
        self.assertEqual(res[1], "  company.employees.*")

    def test_1(self):
        res = core.SqlBuilder.SELECT_DISTINCT(
            CompanySchema.employees.id, CompanySchema.employees.name
        ).get_sql_parts(2)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0], "SELECT DISTINCT")
        self.assertEqual(res[1], "  company.employees.id,")
        self.assertEqual(res[2], "  company.employees.name")

    def test_2(self):
        res = core.SqlBuilder.SELECT(CompanySchema.employees.ALL).get_sql()
        self.assertEqual(res, "SELECT company.employees.*")


class TestFrom(unittest.TestCase):
    def test_0(self):
        res = core.SqlBuilder.SELECT("*").FROM(EmployeesTable)
        sql = res.get_sql()
        self.assertIsInstance(sql, str)
        self.assertEqual(sql, "SELECT * FROM employees")


class TestCondition(unittest.TestCase):
    def test_0(self):
        res = core.Criterion(
            EmployeesTable.name, "=", EmployeesTable.dept
        ).get_sql_parts(0)
        self.assertEqual(res, "employees.name = employees.dept")


class TestFrom(unittest.TestCase):
    def test_0(self):
        res = (
            core.SqlBuilder.SELECT("*")
            .FROM(EmployeesTable)
            .WHERE(core.Criterion("1", "=", "1"))
        )
        sql = res.get_sql()
        self.assertIsInstance(sql, str)
        self.assertEqual(sql, "SELECT * FROM employees WHERE 1 = 1")


# class TestCondition(unittest.TestCase):
#     def test_with_params(self):
#         cond = core.Condition(
#             CompanySchema.employees.pk, "=", core.Param("emp_id")
#         )
#         cond.get_parts(0)
#         SQL.SELECT("*").FROM(CompanySchema.employees).WHERE(
#             core.Condition(
#                 CompanySchema.employees.id, "=", core.Param("emp_id")
#             ).AND(CompanySchema.employees.)
#         ).LIMIT(1)


if __name__ == "__main__":
    unittest.main()
