from dataclasses import dataclass


@dataclass
class CompressionResult:
    data: bytes
    file_name: str
    format: str
    method: str
    file_size: int
    width: int | None
    height: int | None
    target_size: int
    dimension_capped: bool = False
    quality: int | None = None
    near_lossless_level: int | None = None
    subsampling: str | None = None
    scale: float | None = None

    def meets_target(self) -> bool:
        return self.file_size <= self.target_size

    def is_smaller_than(self, source_size: int) -> bool:
        return self.file_size < source_size
