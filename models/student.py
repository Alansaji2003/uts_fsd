"""Student model — id, name, email, password, list of Subjects."""
import random
from .subject import Subject


class Student:
    MAX_SUBJECTS = 4

    def __init__(self, name: str, email: str, password: str):
        self.id = f"{random.randint(1, 999999):06d}"   # 000001..999999
        self.name = name
        self.email = email
        self.password = password
        self.subjects: list[Subject] = []

    # --- enrolment ---------------------------------------------------------
    def can_enrol(self) -> bool:
        return len(self.subjects) < self.MAX_SUBJECTS

    def enrol(self) -> Subject:
        subject = Subject()
        # ensure unique id within this student's enrolment
        existing = {s.id for s in self.subjects}
        while subject.id in existing:
            subject = Subject()
        self.subjects.append(subject)
        return subject

    def remove_subject(self, subject_id: str) -> bool:
        for s in self.subjects:
            if s.id == subject_id:
                self.subjects.remove(s)
                return True
        return False

    # --- marks / grade -----------------------------------------------------
    @property
    def average_mark(self) -> float:
        if not self.subjects:
            return 0.0
        return sum(s.mark for s in self.subjects) / len(self.subjects)

    @property
    def overall_grade(self) -> str:
        avg = self.average_mark
        if avg >= 85: return "HD"
        if avg >= 75: return "D"
        if avg >= 65: return "C"
        if avg >= 50: return "P"
        return "Z"

    @property
    def passed(self) -> bool:
        return self.average_mark >= 50

    # --- password ----------------------------------------------------------
    def change_password(self, new_password: str):
        self.password = new_password

    # --- display -----------------------------------------------------------
    def __repr__(self):
        # "John Smith :: 673358 --> Email: john.smith@university.com"
        return f"{self.name} :: {self.id} --> Email: {self.email}"

    def grade_line(self) -> str:
        # "John Smith :: 673358 --> GRADE:   C - MARK: 68.25"
        return (f"{self.name} :: {self.id} --> "
                f"GRADE:  {self.overall_grade:>2} - MARK: {self.average_mark:.2f}")
