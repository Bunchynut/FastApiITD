import shutil
from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, UploadFile, Depends
from kombu.exceptions import OperationalError
from PIL import Image, UnidentifiedImageError

from src.api.dependencies import require_admin
from src.tasks.tasks import resize_image
from src.upload_limits import MAX_IMAGE_FILE_BYTES, MAX_IMAGE_PIXELS

router = APIRouter(prefix="/images", tags=["Изображения отелей"])

_WINDOWS_DEVICE_NAME = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])$", re.IGNORECASE
)
_INVALID_WINDOWS_CHARS = set('<>:"/\\|?*')
_THUMBNAIL_SUFFIX = "_1000px"
_MAX_COMPONENT_UNITS = 255


def _valid_image_filename(filename: str) -> bool:
    if (
        not filename
        or Path(filename).name != filename
        or any(
            char in _INVALID_WINDOWS_CHARS or ord(char) < 32 for char in filename
        )
        or filename.endswith((".", " "))
    ):
        return False

    stem = filename.split(".", 1)[0].rstrip(" .")
    if _WINDOWS_DEVICE_NAME.fullmatch(stem):
        return False

    try:
        derivative = (
            f"{Path(filename).stem}{_THUMBNAIL_SUFFIX}{Path(filename).suffix}"
        )
        return len(derivative.encode("utf-16-le")) // 2 <= _MAX_COMPONENT_UNITS
    except UnicodeEncodeError:
        return False


@router.post('', dependencies=[Depends(require_admin)])
def upload_image(file: UploadFile):
    filename = file.filename or ""
    if not _valid_image_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid image filename")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_IMAGE_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Image file is too large")

    try:
        with Image.open(file.file) as image:
            image_format = image.format
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=413, detail="Image dimensions are too large"
                )
            image.verify()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
    ) as error:
        raise HTTPException(status_code=400, detail="Invalid image file") from error

    file.file.seek(0)
    try:
        with Image.open(file.file) as image:
            image.load()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
    ) as error:
        raise HTTPException(status_code=400, detail="Invalid image file") from error

    if (
        not image_format
        or Image.registered_extensions().get(Path(filename).suffix.lower())
        != image_format
    ):
        raise HTTPException(
            status_code=400, detail="Image extension does not match its content"
        )

    image_directory = Path("src/static/images")
    image_directory.mkdir(parents=True, exist_ok=True)
    target = image_directory / filename
    if target.resolve().parent != image_directory.resolve():
        raise HTTPException(status_code=400, detail="Invalid image filename")

    file.file.seek(0)
    try:
        with target.open("xb") as destination:
            shutil.copyfileobj(file.file, destination)
    except FileExistsError as error:
        raise HTTPException(
            status_code=409, detail="Image filename already exists"
        ) from error
    image_path = f"src/static/images/{filename}"

    try:
        resize_image.delay(image_path)
    except (OperationalError, OSError) as error:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503, detail="Image processing is unavailable"
        ) from error
