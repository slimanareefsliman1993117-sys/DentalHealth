"""Remove uploaded personal files after their database record is committed away."""
from django.db import transaction
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver
from .models import PatientProfile, StudentProfile, DoctorProfile, Case


MODELS = (PatientProfile, StudentProfile, DoctorProfile, Case)


def remove_after_commit(field):
    if field and field.name:
        storage, name = field.storage, field.name
        transaction.on_commit(lambda: storage.delete(name))


@receiver(post_delete)
def deleted_upload(sender, instance, **kwargs):
    if sender in MODELS:
        remove_after_commit(instance.photos if sender is Case else instance.profile_image)


@receiver(pre_save)
def replaced_upload(sender, instance, **kwargs):
    if sender not in MODELS or not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).first()
    if old:
        name = 'photos' if sender is Case else 'profile_image'
        previous, current = getattr(old, name), getattr(instance, name)
        if previous.name != current.name:
            instance._previous_upload = previous


@receiver(post_save)
def saved_upload(sender, instance, **kwargs):
    previous = getattr(instance, '_previous_upload', None)
    if sender in MODELS and previous:
        del instance._previous_upload
        remove_after_commit(previous)
