# src/aws_src_sample/models/instructor_portal_models.py
import typing

from pydantic import BaseModel, Field

from aws_src_sample.utils.base_types import UserId

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
