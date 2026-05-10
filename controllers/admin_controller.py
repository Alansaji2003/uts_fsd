"""Admin CLI controller — list / group / partition / remove / clear."""
from collections import defaultdict
from models.database import Database


IND = "\t"


class AdminController:

    @classmethod
    def menu(cls):
        while True:
            choice = input(f"{IND}Admin System (c/g/p/r/s/x): ").strip().lower()
            if choice == "s":
                cls._show()
            elif choice == "g":
                cls._group()
            elif choice == "p":
                cls._partition()
            elif choice == "r":
                cls._remove()
            elif choice == "c":
                cls._clear()
            elif choice == "x":
                return

    # ------------------------------------------------------------------ show
    @classmethod
    def _show(cls):
        students = Database.read_all()
        print(f"{IND}Student List")
        if not students:
            print(f"{IND}\t< Nothing to Display >")
            return
        for s in students:
            print(f"{IND}{s}")

    # ------------------------------------------------------------------ group
    @classmethod
    def _group(cls):
        students = Database.read_all()
        print(f"{IND}Grade Grouping")
        if not students:
            print(f"{IND}\t< Nothing to Display >")
            return
        groups: dict[str, list] = defaultdict(list)
        for s in students:
            groups[s.overall_grade].append(s.grade_line())
        for grade, members in groups.items():
            joined = ", ".join(members)
            print(f"{IND}{grade:<2} --> [{joined}]")

    # ------------------------------------------------------------------ partition
    @classmethod
    def _partition(cls):
        students = Database.read_all()
        print(f"{IND}PASS/FAIL Partition")
        passed = [s.grade_line() for s in students if s.passed]
        failed = [s.grade_line() for s in students if not s.passed]
        print(f"{IND}FAIL --> [{', '.join(failed)}]")
        print(f"{IND}PASS --> [{', '.join(passed)}]")

    # ------------------------------------------------------------------ remove
    @classmethod
    def _remove(cls):
        sid = input(f"{IND}Remove by ID: ").strip()
        # normalise — accept "1" as "000001" if user types short
        sid = sid.zfill(6) if sid.isdigit() else sid
        if Database.remove_by_id(sid):
            print(f"{IND}Removing Student {sid} Account")
        else:
            print(f"{IND}Student {sid} does not exist")

    # ------------------------------------------------------------------ clear
    @classmethod
    def _clear(cls):
        print(f"{IND}Clearing students database")
        confirm = input(f"{IND}Are you sure you want to clear the database (Y)ES/(N)O: ").strip().upper()
        if confirm == "Y":
            Database.clear()
            print(f"{IND}Students data cleared")
