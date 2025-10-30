import datetime
import typing

import pydantic

from thoughtful_backend.utils.base_types import IsoTimestamp, LessonId, SectionId, UserId

AssessmentLevel = typing.Literal["achieves", "mostly", "developing", "insufficient"]


class ChatBotFeedback(typing.NamedTuple):
    aiFeedback: str
    aiAssessment: AssessmentLevel


class ReflectionInteractionInputModel(pydantic.BaseModel):
    """
    Pydantic model for the request body of POST /lessons/.../reflections.
    Matches ReflectionInteractionInput in Swagger.
    """

    userTopic: str
    isUserTopicPredefined: bool
    userCode: str
    isUserCodePredefined: bool
    userExplanation: str
    isFinal: bool = False
    sourceVersionId: typing.Optional[str] = None

    class Config:
        # Pydantic V2: from_attributes = True (if creating from ORM models, not relevant here)
        extra = "forbid"  # Disallow extra fields in request


class ReflectionVersionItemModel(pydantic.BaseModel):
    """
    Pydantic model representing a reflection version item stored in DynamoDB.
    Aligns with ReflectionVersionItem in Swagger.
    """

    versionId: str = pydantic.Field(description="Unique identifier (SK): lessonId#sectionId#createdAtISO")
    userId: UserId = pydantic.Field(description="Partition Key")
    lessonId: LessonId
    sectionId: SectionId
    userTopic: str
    userCode: str
    userExplanation: str
    aiFeedback: typing.Optional[str] = None
    aiAssessment: typing.Optional[AssessmentLevel] = None
    createdAt: IsoTimestamp  # ISO8601 string.
    isFinal: bool
    sourceVersionId: typing.Optional[str] = None
    finalEntryCreatedAt: typing.Optional[IsoTimestamp] = None

    @pydantic.field_validator("createdAt", "finalEntryCreatedAt", mode="before")
    @classmethod
    def ensure_iso_format_with_z(cls, v: typing.Any, info: pydantic.ValidationInfo) -> typing.Optional[str]:
        field_name = info.field_name if info else "UnknownField"

        if v is None:
            assert field_name != "createdAt", "Should not be reached for createdAt if it's mandatory"
            return None

        if isinstance(v, datetime.datetime):
            if v.tzinfo is None:
                v_utc = v.replace(tzinfo=datetime.timezone.utc)
            else:
                v_utc = v.astimezone(datetime.timezone.utc)
            return v_utc.isoformat().replace("+00:00", "Z")

        if isinstance(v, str):
            try:
                if v.endswith("Z"):
                    # Ensure it's parsed as UTC
                    dt_obj = datetime.datetime.fromisoformat(v[:-1] + "+00:00")
                else:
                    # Try parsing directly, assuming it might have offset or be naive
                    dt_obj = datetime.datetime.fromisoformat(v)

                if dt_obj.tzinfo is None:  # If naive, assume UTC
                    dt_obj_utc = dt_obj.replace(tzinfo=datetime.timezone.utc)
                else:  # If aware, convert to UTC
                    dt_obj_utc = dt_obj.astimezone(datetime.timezone.utc)

                return dt_obj_utc.isoformat().replace("+00:00", "Z")
            except ValueError:
                raise ValueError(
                    f"{field_name} ('{v}') is not a valid ISO8601 string that can be parsed to a datetime object."
                )
        raise TypeError(f"Unsupported type for {field_name}: {type(v)}. Expected datetime object or ISO8601 string.")


class ListOfReflectionDraftsResponseModel(pydantic.BaseModel):
    """
    Pydantic model for GET /lessons/.../reflections response.
    Matches ListOfReflectionVersionsResponse in your Swagger.
    """

    versions: list[ReflectionVersionItemModel]
    lastEvaluatedKey: typing.Optional[dict[str, typing.Any]] = None


class ListOfFinalLearningEntriesResponseModel(pydantic.BaseModel):
    """
    Pydantic model for GET /learning-entries response.
    Matches ListOfReflectionVersionsResponse in your Swagger for this path,
    where items are ReflectionVersionItemModel with isFinal=true.
    """

    entries: list[ReflectionVersionItemModel]  # Items will have isFinal=true
    lastEvaluatedKey: typing.Optional[dict[str, typing.Any]] = None
