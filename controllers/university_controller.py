"""Top-level University System menu."""
from .student_controller import StudentController
from .admin_controller import AdminController


class UniversityController:

    @classmethod
    def run(cls):
        while True:
            choice = input("University System: (A)dmin, (S)tudent, or X : ").strip().upper()
            if choice == "A":
                AdminController.menu()
            elif choice == "S":
                StudentController.menu()
            elif choice == "X":
                print("Thank You")
                return
