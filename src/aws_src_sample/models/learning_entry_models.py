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
    def ensure_iso_format_with_z(cls, v, field):
        if v is None and field.name == "finalEntryCreatedAt":  # finalEntryCreatedAt can be None
            return None
        if isinstance(v, datetime.datetime):
            # Ensure it's timezone-aware (UTC) and has 'Z'
            if v.tzinfo is None:
                v = v.replace(tzinfo=datetime.timezone.utc)
            else:
                v = v.astimezone(datetime.timezone.utc)
            return v.isoformat().replace("+00:00", "Z")
        if isinstance(v, str):
            # Basic check, can be more robust
            if not v.endswith("Z"):
                # Attempt to parse and reformat if possible, or raise error for strictness
                try:
                    dt_obj = datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
                    return dt_obj.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
                except ValueError:
                    raise ValueError(
                        f"{field.name} must be a valid ISO8601 string ending with Z, or a datetime object."
                    )
            return v
        if v is None and field.name == "createdAt":  # createdAt should not be None
            raise ValueError(f"{field.name} cannot be None.")

        raise TypeError(f"Unsupported type for {field.name}: {type(v)}")

    class Config:
        use_enum_values = True  # For AssessmentLevel enum
        # Pydantic V2: from_attributes = True


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
    Matches ReflectionFeedbackAndVersionResponse in your latest Swagger (renamed for clarity).
    """

    draftEntry: ReflectionVersionItemModel  # This is the DDB item model
    currentAiFeedback: str
    currentAiAssessment: AssessmentLevel  # Pydantic will handle enum serialization

    class Config:
        use_enum_values = True


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
