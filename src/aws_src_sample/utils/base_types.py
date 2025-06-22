import typing

UserId = typing.NewType("UserId", str)
InstructorId = typing.NewType("InstructorId", str)
AccessTokenId = typing.NewType("AccessTokenId", str)
RefreshTokenId = typing.NewType("RefreshTokenId", str)

UnitId = typing.NewType("UnitId", str)
LessonId = typing.NewType("LessonId", str)
SectionId = typing.NewType("SectionId", str)
IsoTimestamp = typing.NewType("IsoTimestamp", str)
