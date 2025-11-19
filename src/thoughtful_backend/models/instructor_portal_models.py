# src/aws_src_sample/models/instructor_portal_models.py
import typing

from pydantic import BaseModel

from thoughtful_backend.models.user_progress_models import SectionCompletionDetail
from thoughtful_backend.utils.base_types import (
    LessonId,
    SectionId,
    UnitId,
    UserId,
)

# Assuming UserId is a type alias or NewType for str, defined elsewhere (e.g., base_types)
# If not, define it here or import appropriately. For now, let's use str.
# from ..utils.base_types import UserId # Example if you have it


class InstructorStudentInfoModel(BaseModel):
    studentId: UserId
    studentName: typing.Optional[str]
    studentEmail: typing.Optional[str]


class ListOfInstructorStudentsResponseModel(BaseModel):
    students: list[InstructorStudentInfoModel]
    # lastEvaluatedKey: typing.Optional[dict] = None # For future pagination if needed


class StudentUnitCompletionDataModel(BaseModel):
    studentId: UserId
    # studentName: typing.Optional[str] = Field(None, alias="studentName") # Client can map this from ListOfInstructorStudents
    # Key is full lessonId (e.g., "00_intro/lesson_1")
    completedSectionsInUnit: dict[LessonId, dict[SectionId, SectionCompletionDetail]]


class ClassUnitProgressResponseModel(BaseModel):
    unitId: UnitId
    # unitTitle: typing.Optional[str] = Field(None, alias="unitTitle") # Client has this from its own data
    studentProgressData: list[StudentUnitCompletionDataModel]
    # lastEvaluatedKey for student pagination within this response could be added later


# Models for displaying progress (client-side computed, but good for reference)
class StudentLessonProgressItemModel(BaseModel):
    lessonId: LessonId
    lessonTitle: str
    completionPercent: float
    isCompleted: bool
    completedSectionsCount: int
    totalRequiredSectionsInLesson: int


class StudentUnitProgressResponseModel_ClientView(BaseModel):  # What client computes and displays
    studentId: UserId
    studentName: typing.Optional[str]
    unitId: UnitId
    unitTitle: str
    lessonsProgress: list[StudentLessonProgressItemModel]
    overallUnitCompletionPercent: float


class SectionStatusItemModel(BaseModel):
    sectionId: SectionId
    sectionTitle: str
    sectionKind: str
    status: typing.Literal["completed", "submitted", "not_started"]
    submissionTimestamp: typing.Optional[str]
    submissionDetails: typing.Optional[typing.Any]


class LessonProgressProfileModel(BaseModel):
    lessonId: LessonId
    lessonTitle: str
    sections: list[SectionStatusItemModel]


class UnitProgressProfileModel(BaseModel):
    unitId: UnitId
    unitTitle: str
    lessons: list[LessonProgressProfileModel]


class StudentDetailedProgressResponseModel(BaseModel):
    studentId: UserId
    studentName: typing.Optional[str]
    profile: list[UnitProgressProfileModel]
