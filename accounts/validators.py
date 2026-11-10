"""Shared validation for REST requests and Django administration forms."""
from datetime import date
from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_birthdate(value):
    if value and value > date.today():
        raise ValidationError(_('Birthdate cannot be in the future.'), code='future_birthdate')


def validate_medical_image(value):
    if not value:
        return
    if value.size > 5 * 1024 * 1024:
        raise ValidationError(_('Images must be at most 5 MiB.'), code='image_size')
    # Django form/REST ImageField has already verified newly uploaded images.
    # Stored FieldFiles also pass model validation, so inspect those separately.
    image = getattr(value, 'image', None)
    try:
        if image is not None:
            image_format, width, height = image.format, image.width, image.height
        else:
            try:
                with Image.open(value) as stored_image:
                    image_format = stored_image.format
                    width, height = stored_image.size
                    stored_image.verify()
            finally:
                value.seek(0)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValidationError(_('Upload a valid image.'), code='invalid_image') from error
    if image_format not in {'JPEG', 'PNG', 'WEBP'}:
        raise ValidationError(_('Use a JPEG, PNG, or WebP image.'), code='image_format')
    if width * height > 20_000_000:
        raise ValidationError(_('Images must be at most 20 megapixels.'), code='image_dimensions')
