import asyncio
import filecmp
import math
import tempfile

from PIL import Image
import os

from src.DataBase import async_session_maker, async_session_maker_null_pull
from src.tasks.celery_app import celery_app
from src.utils.db_manager import DBManager


@celery_app.task
def resize_image(image_path: str):
    sizes = [1000, 500, 200]
    output_folder = os.path.join('src', 'static', 'images', 'thumbnails')
    max_dimension = 1000
    max_pixels = 1_000_000

    with Image.open(image_path) as img:
        img.load()
        original_width, original_height = img.size
        image_format = img.format
        if image_format is None:
            image_format = Image.registered_extensions().get(
                os.path.splitext(image_path)[1].lower()
            )
        if image_format is None:
            raise ValueError(f"Cannot determine image format for {image_path}")

        base_name = os.path.basename(image_path)
        name, ext = os.path.splitext(base_name)
        os.makedirs(output_folder, exist_ok=True)

        for size in sizes:
            scale = min(
                size / original_width,
                max_dimension / original_width,
                max_dimension / original_height,
                math.sqrt(max_pixels / (original_width * original_height)),
            )
            width = max(1, min(max_dimension, round(original_width * scale)))
            height = max(1, min(max_dimension, round(original_height * scale)))
            while width * height > max_pixels:
                if width >= height:
                    width -= 1
                else:
                    height -= 1

            new_file_name = f"{name}_{size}px{ext}"
            output_path = os.path.join(output_folder, new_file_name)
            with img.resize((width, height), Image.Resampling.LANCZOS) as img_resized:
                temporary_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb", prefix=".thumb-", dir=output_folder, delete=False
                    ) as temporary:
                        temporary_path = temporary.name
                        img_resized.save(temporary, format=image_format)

                    existing_matches = os.path.exists(output_path) and filecmp.cmp(
                        temporary_path, output_path, shallow=False
                    )

                    if existing_matches:
                        os.unlink(temporary_path)
                    else:
                        os.replace(temporary_path, output_path)
                finally:
                    if temporary_path and os.path.exists(temporary_path):
                        os.unlink(temporary_path)

    print(f"Изображение сохранено в следующих размерах: {sizes} в папке {output_folder}")


async def get_booking_with_today_checkin_helper():
    print('Запускаюсь')
    async with DBManager(session_factory=async_session_maker_null_pull) as db:
        bookings = await db.booking.get_booking_today_checkin()
        print(f'{bookings}')

@celery_app.task(name='booking_today_checkin')
def send_email_booking_today_checkin():
    asyncio.run(get_booking_with_today_checkin_helper())
