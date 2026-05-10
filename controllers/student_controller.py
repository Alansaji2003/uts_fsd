"""Student CLI controller — register / login flows."""
from models.student import Student
from models.database import Database
from utils.validators import (
    is_valid_email, is_valid_password, name_from_email
)
from .subject_controller import SubjectController


IND = "\t"   # indentation for sub-menu lines


class StudentController:

    @classmethod
    def menu(cls):
        while True:
            choice = input(f"{IND}Student System (l/r/x): ").strip().lower()
            if choice == "l":
                cls._login()
            elif choice == "r":
                cls._register()
            elif choice == "x":
                return
            # silently ignore unknown input (matches sample behaviour)

    # ------------------------------------------------------------------ register
    @classmethod
    def _register(cls):
        print(f"{IND}Student Sign Up")
        email, password = cls._prompt_credentials()

        # check already exists
        existing = Database.find_by_email(email)
        if existing is not None:
            print(f"{IND}Student {existing.name} already exists")
            return

        name = name_from_email(email)
        print(f"{IND}Name: {name}")
        print(f"{IND}Enrolling Student {name}")
        student = Student(name=name, email=email, password=password)
        Database.add_student(student)

    # ------------------------------------------------------------------ login
    @classmethod
    def _login(cls):
        print(f"{IND}Student Sign In")
        email, password = cls._prompt_credentials()

        student = Database.find_by_email(email)
        if student is None or student.password != password:
            print(f"{IND}Student does not exist")
            return

        # Re-fetch fresh copy so changes persist correctly via update
        SubjectController.menu(student)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _prompt_credentials() -> tuple[str, str]:
        """Loop until email + password both pass format validation."""
        while True:
            email = input(f"{IND}Email: ").strip()
            password = input(f"{IND}Password: ").strip()
            if is_valid_email(email) and is_valid_password(password):
                print(f"{IND}email and password formats acceptable")
                return email, password
            print(f"{IND}Incorrect email or password format")
