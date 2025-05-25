import datetime
import typing

import pydantic

AssessmentLevel = typing.Literal["achieves", "mostly", "developing", "insufficient"]


class ChatBotFeedback(typing.NamedTuple):
    aiFeedback: str
    aiAssessment: AssessmentLevel


class ReflectionVersionItemModel(pydantic.BaseModel):
    """
    Pydantic model representing a reflection version item stored in DynamoDB.
    Aligns with ReflectionVersionItem in Swagger.
    """

    versionId: str = pydantic.Field(description="Unique identifier (SK): lessonId#sectionId#createdAtISO")
    userId: str = pydantic.Field(description="Partition Key")
    lessonId: str
    sectionId: str
    userTopic: str
    userCode: str
    userExplanation: str
    createdAt: str  # ISO8601 string. Consider using datetime and validating/serializing.
    isFinal: bool

    aiFeedback: typing.Optional[str] = None
    aiAssessment: typing.Optional[AssessmentLevel] = None

    # Attribute for GSI for final entries. Only populated if isFinal is true.
    # Value is the same as createdAt for that final entry.
    finalEntryCreatedAt: typing.Optional[str] = None

    @pydantic.field_validator("createdAt", "finalEntryCreatedAt", mode="before")
    def ensure_iso_format_with_z(cls, v: typing.Any, info: pydantic.ValidationInfo) -> typing.Optional[str]:
        field_name = info.field_name  # Get the field name from the info object

        if v is None:
            if field_name == "finalEntryCreatedAt":  # finalEntryCreatedAt can be None
                return None
            elif field_name == "createdAt":  # createdAt should not be None
                # This check should ideally be handled by Pydantic's own required field validation
                # if 'createdAt' is not Optional and has no default.
                # However, keeping it here for explicit pre-validation is also possible.
                raise ValueError(f"{field_name} cannot be None.")
            return None  # Should not be reached if only validating these two fields

        if isinstance(v, datetime.datetime):
            # Ensure it's timezone-aware (UTC) and has 'Z'
            if v.tzinfo is None:
                v_utc = v.replace(tzinfo=datetime.timezone.utc)
            else:
                v_utc = v.astimezone(datetime.timezone.utc)
            return v_utc.isoformat().replace("+00:00", "Z")

        if isinstance(v, str):
            # Attempt to parse and reformat to ensure it's UTC and ends with 'Z'
            try:
                # Handle if 'Z' is already there or if it needs +00:00 for parsing
                if v.endswith("Z"):
                    dt_obj = datetime.datetime.fromisoformat(v[:-1] + "+00:00")
                else:
                    dt_obj = datetime.datetime.fromisoformat(v)  # Try parsing directly

                # Ensure it's UTC after parsing
                if dt_obj.tzinfo is None:
                    dt_obj_utc = dt_obj.replace(tzinfo=datetime.timezone.utc)
                else:
                    dt_obj_utc = dt_obj.astimezone(datetime.timezone.utc)

                reformatted_v = dt_obj_utc.isoformat().replace("+00:00", "Z")
                return reformatted_v
            except ValueError:
                raise ValueError(
                    f"{field_name} ('{v}') is not a valid ISO8601 string that can be parsed to a datetime object."
                )

        # If 'v' is not None, not a datetime, and not a string, it's an unsupported type for this validator.
        raise TypeError(f"Unsupported type for {field_name}: {type(v)}. Expected datetime object or ISO8601 string.")


class ReflectionInteractionInputModel(pydantic.BaseModel):
    """
    Pydantic model for the request body of POST /lessons/.../reflections.
    Matches ReflectionInteractionInput in Swagger.
    """

    userTopic: str
    userCode: str
    userExplanation: str  # Name from your latest Swagger
    isFinal: bool = False
    sourceVersionId: typing.Optional[str] = None

    class Config:
        # Pydantic V2: from_attributes = True (if creating from ORM models, not relevant here)
        extra = "forbid"  # Disallow extra fields in request


class ReflectionFeedbackAndDraftResponseModel(pydantic.BaseModel):
    """
    Pydantic model for the response when a draft is created (isFinal=false).
    """

    draftEntry: ReflectionVersionItemModel  # This is the DDB item model
    aiFeedback: str
    aiAssessment: AssessmentLevel  # Pydantic will handle enum serialization


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
