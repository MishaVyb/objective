from typing import IO, Any, List, Mapping, Optional, Sequence, Tuple, Union

# for some reason httpx keeps these types in private module
HeaderTypes = (
    Mapping[str, str]
    | Mapping[bytes, bytes]
    | Sequence[Tuple[str, str]]
    | Sequence[Tuple[bytes, bytes]]
)

PrimitiveData = Optional[str | int | float | bool]

QueryParamTypes = (
    Mapping[str, PrimitiveData | Sequence[PrimitiveData]]
    | List[Tuple[str, PrimitiveData]]
    | Tuple[Tuple[str, PrimitiveData], ...]
    | str
    | bytes
)

RequestData = Mapping[str, Any]

FileContent = Union[IO[bytes], bytes, str]
FileTypes = Union[
    # file (or bytes)
    FileContent,
    # (filename, file (or bytes))
    Tuple[Optional[str], FileContent],
    # (filename, file (or bytes), content_type)
    Tuple[Optional[str], FileContent, Optional[str]],
    # (filename, file (or bytes), content_type, headers)
    Tuple[Optional[str], FileContent, Optional[str], Mapping[str, str]],
]
RequestFiles = Union[Mapping[str, FileTypes], Sequence[Tuple[str, FileTypes]]]

TimeoutTypes = (
    Optional[float]
    | Tuple[Optional[float] | Optional[float] | Optional[float] | Optional[float]]
)
