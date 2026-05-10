"""Subject Enrolment menu — runs after a successful student login."""
from models.student import Student
from models.database import Database
from utils.validators import is_valid_password


IND = "\t"


class SubjectController:

    @classmethod
    def menu(cls, student: Student):
        while True:
            choice = input(f"{IND}Student Course Menu (c/e/r/s/x): ").strip().lower()
            if choice == "c":
                cls._change_password(student)
            elif choice == "e":
                cls._enrol(student)
            elif choice == "r":
                cls._remove(student)
            elif choice == "s":
                cls._show(student)
            elif choice == "x":
                return

    # ------------------------------------------------------------------ enrol
    @classmethod
    def _enrol(cls, student: Student):
        if not student.can_enrol():
            print(f"{IND}Students are allowed to enrol in 4 subjects only")
            return
        subject = student.enrol()
        print(f"{IND}Enrolling in Subject-{subject.id}")
        print(f"{IND}You are now enrolled in {len(student.subjects)} out of 4 subjects")
        Database.update_student(student)

    # ------------------------------------------------------------------ remove
    @classmethod
    def _remove(cls, student: Student):
        sid = input(f"{IND}Remove Subject by ID: ").strip()
        # normalise to 3-digit
        sid = sid.zfill(3) if sid.isdigit() else sid
        if student.remove_subject(sid):
            # NOTE: spec sample uses 'Droping' (single p) — kept verbatim.
            print(f"{IND}Droping Subject-{sid}")
            print(f"{IND}You are now enrolled in {len(student.subjects)} out of 4 subjects")
            Database.update_student(student)
        else:
            print(f"{IND}Subject {sid} does not exist")

    # ------------------------------------------------------------------ show
    @classmethod
    def _show(cls, student: Student):
        print(f"{IND}Showing {len(student.subjects)} subjects")
        for s in student.subjects:
            print(f"{IND}{s}")

    # ------------------------------------------------------------------ change pw
    @classmethod
    def _change_password(cls, student: Student):
        print(f"{IND}Updating Password")
        # require valid format on the new password
        while True:
            new_pwd = input(f"{IND}New Password: ").strip()
            if not is_valid_password(new_pwd):
                print(f"{IND}Incorrect password format")
                continue
            break
        while True:
            confirm = input(f"{IND}Confirm Password: ").strip()
            if confirm != new_pwd:
                print(f"{IND}Password does not match - try again")
                continue
            break
        student.change_password(new_pwd)
        Database.update_student(student)
