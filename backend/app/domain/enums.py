from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    HR = "HR"
    TEAMLEAD = "TEAMLEAD"
    EMPLOYEE = "EMPLOYEE"


class SurveyTemplate(str, Enum):
    LIKERT = "LIKERT"
    LUSCHER = "LUSCHER"
    MASLACH = "MASLACH"


class QuestionType(str, Enum):
    LIKERT = "LIKERT"
    LUSCHER_COLOR = "LUSCHER_COLOR"
    MASLACH_SCALE = "MASLACH_SCALE"
    TEXT = "TEXT"
