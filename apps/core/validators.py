from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

html_file_validator = FileExtensionValidator(allowed_extensions=["html"])
css_file_validator = FileExtensionValidator(allowed_extensions=["css"])

MAX_FILE_SIZE_BYTES = 500 * 1024


def validate_file_size(file):
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"File size must not exceed {MAX_FILE_SIZE_BYTES / 1024:.0f} KB. "
            f"Uploaded file is {file.size / 1024:.1f} KB."
        )
