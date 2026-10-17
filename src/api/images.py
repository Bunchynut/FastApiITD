import shutil
from fastapi import APIRouter, Depends, UploadFile

from src.api.dependencies import require_admin
from src.tasks.tasks import resize_image

router = APIRouter(prefix="/images", tags=["Изображения отелей"])


@router.post('', dependencies=[Depends(require_admin)])
def upload_image(file: UploadFile):
    image_path = f'src/static/images/{file.filename}'
    with open(image_path, 'wb+') as new_file:
        shutil.copyfileobj(file.file, new_file)

    resize_image.delay(image_path)
