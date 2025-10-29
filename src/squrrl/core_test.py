from . import core

import unittest


class EmployeesTable(core.Table):
    class Meta:
        table_name = "employees"

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
    class Meta:
        schema_name = "company"

    user_defined_stuff = 10

    employees = EmployeesTable
    deptinfo = Dept_Info


class TestPath(unittest.TestCase):
    def test_path(self):
        def shit(a: type[core.Table]):
            pass
            # print(a.get_path())

        # print(type(CompanySchema))
        # print(CompanySchema.employees)
        # print(CompanySchema.employees.user_defined_stuff)
        shit(CompanySchema.employees)  # Type hint check

        self.assertEqual(Dept_Info.get_path(), "dept_info")
        self.assertEqual(Dept_Info.desc.get_path(), "dept_info.desc")
        self.assertEqual(EmployeesTable.get_path(), "employees")
        self.assertEqual(EmployeesTable.id.get_path(), "employees.id")
        self.assertEqual(
            CompanySchema.employees.get_path(), "company.employees"
        )
        self.assertEqual(
            CompanySchema.employees.id.get_path(), "company.employees.id"
        )
        self.assertEqual(CompanySchema.deptinfo.get_path(), "company.dept_info")
        self.assertEqual(
            CompanySchema.deptinfo.dept.get_path(), "company.dept_info.dept"
        )


class TestCondition(unittest.TestCase):
    def test_with_params(self):
        cond = core.Condition(
            CompanySchema.employees.pk, "=", core.Param("emp_id")
        )
        cond.get_parts(0)
        SQL.SELECT("*").FROM(CompanySchema.employees).WHERE(
            core.Condition(
                CompanySchema.employees.id, "=", core.Param("emp_id")
            ).AND(CompanySchema.employees.)
        ).LIMIT(1)


if __name__ == "__main__":
    unittest.main()
