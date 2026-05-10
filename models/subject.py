"""Subject model — random 3-digit id, mark 25-100, grade derived from mark."""
import random


class Subject:
    def __init__(self):
        self.id = f"{random.randint(1, 999):03d}"   # 001..999
        self.mark = random.randint(25, 100)
        self.grade = self._calculate_grade(self.mark)

    @staticmethod
    def _calculate_grade(mark: float) -> str:
        if mark >= 85:
            return "HD"
        if mark >= 75:
            return "D"
        if mark >= 65:
            return "C"
        if mark >= 50:
            return "P"
        return "Z"

    def __repr__(self):
        # Format: [ Subject::541 -- mark = 55 -- grade =   P ]
        return f"[ Subject::{self.id} -- mark = {self.mark} -- grade =  {self.grade:>2} ]"
