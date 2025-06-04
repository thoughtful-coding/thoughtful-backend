# src/aws_src_sample/models/instructor_portal_models.py
import typing

from pydantic import BaseModel, Field

from aws_src_sample.utils.base_types import (
    IsoTimestamp,
    LessonId,
    SectionId,
    UnitId,
    UserId,
)

# Assuming UserId is a type alias or NewType for str, defined elsewhere (e.g., base_types)
# If not, define it here or import appropriately. For now, let's use str.
# from ..utils.base_types import UserId # Example if you have it


class InstructorStudentInfoModel(BaseModel):
    student_id: UserId = Field(..., alias="studentId")
    student_name: typing.Optional[str] = Field(None, alias="studentName")
    student_email: typing.Optional[str] = Field(None, alias="studentEmail")

    class Config:
        populate_by_name = True
        allow_population_by_field_name = False  # Prefer aliases


class ListOfInstructorStudentsResponseModel(BaseModel):
    students: list[InstructorStudentInfoModel]
    # lastEvaluatedKey: typing.Optional[dict] = None # For future pagination if needed


class StudentUnitCompletionDataModel(BaseModel):
    student_id: UserId = Field(..., alias="studentId")
    # studentName: typing.Optional[str] = Field(None, alias="studentName") # Client can map this from ListOfInstructorStudents
    # Key is full lessonId (e.g., "00_intro/lesson_1")
    completed_sections_in_unit: dict[LessonId, dict[SectionId, IsoTimestamp]] = Field(
        ..., alias="completedSectionsInUnit"
    )

    class Config:
        populate_by_name = True
        allow_population_by_field_name = False


class ClassUnitProgressResponseModel(BaseModel):
    unit_id: UnitId = Field(..., alias="unitId")
    # unitTitle: typing.Optional[str] = Field(None, alias="unitTitle") # Client has this from its own data
    student_progress_data: list[StudentUnitCompletionDataModel] = Field(..., alias="studentProgressData")
    # lastEvaluatedKey for student pagination within this response could be added later

    class Config:
        populate_by_name = True
        allow_population_by_field_name = False


# Models for displaying progress (client-side computed, but good for reference)
class StudentLessonProgressItemModel(BaseModel):
    lesson_id: LessonId = Field(..., alias="lessonId")
    lesson_title: str = Field(..., alias="lessonTitle")
    completion_percent: float = Field(..., alias="completionPercent")
    is_completed: bool = Field(..., alias="isCompleted")
    completed_sections_count: int = Field(..., alias="completedSectionsCount")
    total_required_sections_in_lesson: int = Field(..., alias="totalRequiredSectionsInLesson")

    class Config:
        populate_by_name = True
        allow_population_by_field_name = False


class StudentUnitProgressResponseModel_ClientView(BaseModel):  # What client computes and displays
    student_id: UserId = Field(..., alias="studentId")
    student_name: typing.Optional[str] = Field(None, alias="studentName")
    unit_id: UnitId = Field(..., alias="unitId")
    unit_title: str = Field(..., alias="unitTitle")
    lessons_progress: list[StudentLessonProgressItemModel] = Field(..., alias="lessonsProgress")
    overall_unit_completion_percent: float = Field(..., alias="overallUnitCompletionPercent")

    class Config:
        populate_by_name = True
        allow_population_by_field_name = False
