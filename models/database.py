"""Database — pickle-backed persistence for Student objects in students.data"""
import os
import pickle
from .student import Student


class Database:
    FILE_NAME = "students.data"

    @classmethod
    def _ensure_file(cls):
        if not os.path.exists(cls.FILE_NAME):
            with open(cls.FILE_NAME, "wb") as f:
                pickle.dump([], f)

    # --- read --------------------------------------------------------------
    @classmethod
    def read_all(cls) -> list[Student]:
        cls._ensure_file()
        try:
            with open(cls.FILE_NAME, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, list):
                return []
            return data
        except (EOFError, pickle.UnpicklingError):
            return []

    # --- write -------------------------------------------------------------
    @classmethod
    def write_all(cls, students: list[Student]):
        cls._ensure_file()
        with open(cls.FILE_NAME, "wb") as f:
            pickle.dump(students, f)

    # --- helpers -----------------------------------------------------------
    @classmethod
    def find_by_email(cls, email: str) -> Student | None:
        for s in cls.read_all():
            if s.email.lower() == (email or "").lower():
                return s
        return None

    @classmethod
    def find_by_id(cls, sid: str) -> Student | None:
        for s in cls.read_all():
            if s.id == sid:
                return s
        return None

    @classmethod
    def add_student(cls, student: Student):
        students = cls.read_all()
        # ensure unique 6-digit id
        existing_ids = {s.id for s in students}
        while student.id in existing_ids:
            import random
            student.id = f"{random.randint(1, 999999):06d}"
        students.append(student)
        cls.write_all(students)

    @classmethod
    def update_student(cls, updated: Student):
        students = cls.read_all()
        for i, s in enumerate(students):
            if s.id == updated.id:
                students[i] = updated
                break
        cls.write_all(students)

    @classmethod
    def remove_by_id(cls, sid: str) -> bool:
        students = cls.read_all()
        for s in students:
            if s.id == sid:
                students.remove(s)
                cls.write_all(students)
                return True
        return False

    @classmethod
    def clear(cls):
        cls.write_all([])
