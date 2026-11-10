from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from datetime import date
from .validators import validate_birthdate, validate_medical_image

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('patient', 'Patient'),
        ('student', 'Student'),
        ('doctor', 'Doctor'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='patient')
    email = models.EmailField(_('email address'), unique=True)
    clinical_access_approved = models.BooleanField(default=False, help_text='Only an administrator may approve clinical access for a doctor.')

    class Meta:
        db_table = 'auth_user'
        constraints = [models.UniqueConstraint(Lower('email'), name='dental_user_email_ci_unique')]
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.username

class Specialty(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class PatientProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    profile_image = models.ImageField(upload_to='profiles/patients/', blank=True, null=True, validators=[validate_medical_image])
    phone = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    birthdate = models.DateField(blank=True, null=True, validators=[validate_birthdate])
    age = models.PositiveIntegerField(blank=True, null=True)
    birthplace = models.CharField(max_length=100, blank=True)
    chronic_diseases = models.TextField(default='nothing')
    additional_info = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.birthdate:
            today = date.today()
            self.age = today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
        else:
            self.age = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Patient Profile"

class StudentProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    SPECIALTY_CHOICES = (
        ('dentistry', 'Dentistry'),
        ('oral_surgery', 'Oral Surgery'),
        ('orthodontics', 'Orthodontics'),
        ('prosthodontics', 'Prosthodontics'),
        ('pediatrics', 'Pediatrics'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    profile_image = models.ImageField(upload_to='profiles/students/', blank=True, null=True, validators=[validate_medical_image])
    phone = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    birthdate = models.DateField(blank=True, null=True, validators=[validate_birthdate])
    age = models.PositiveIntegerField(blank=True, null=True)
    birthplace = models.CharField(max_length=100, blank=True)
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES)
    years_of_teaching = models.PositiveIntegerField(default=1, choices=[(i, i) for i in range(1, 9)])
    wanted_groups = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if self.birthdate:
            today = date.today()
            self.age = today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
        else:
            self.age = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Student Profile"

class DoctorProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    SPECIALTY_CHOICES = (
        ('dentistry', 'Dentistry'),
        ('oral_surgery', 'Oral Surgery'),
        ('orthodontics', 'Orthodontics'),
        ('prosthodontics', 'Prosthodontics'),
        ('pediatrics', 'Pediatrics'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    profile_image = models.ImageField(upload_to='profiles/doctors/', blank=True, null=True, validators=[validate_medical_image])
    phone = models.CharField(max_length=15, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    birthdate = models.DateField(blank=True, null=True, validators=[validate_birthdate])
    age = models.PositiveIntegerField(blank=True, null=True)
    birthplace = models.CharField(max_length=100, blank=True)
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES)
    years_of_teaching = models.PositiveIntegerField(default=1, choices=[(i, i) for i in range(1, 9)])
    wanted_groups = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if self.birthdate:
            today = date.today()
            self.age = today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
        else:
            self.age = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Doctor Profile"

class Case(models.Model):
    PAIN_TYPE_CHOICES = (
        ('throbbing', 'Throbbing'),
        ('sharp', 'Sharp'),
        ('continuous', 'Continuous'),
        ('intermittent', 'Intermittent'),
    )
    PAIN_LOCATION_CHOICES = (
        ('mandible', 'Mandible'),
        ('maxilla', 'Maxilla'),
        ('right', 'Right'),
        ('left', 'Left'),
    )
    PAIN_DURATION_CHOICES = (
        ('less_than_a_day', 'Less than a day'),
        ('1-3_days', '1-3 days'),
        ('a_week', 'A week'),
        ('more_than_a_week', 'More than a week'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )

    patient = models.ForeignKey('User', on_delete=models.CASCADE, related_name='cases', limit_choices_to={'user_type': 'patient'})
    title = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    pain_type = models.CharField(max_length=20, choices=PAIN_TYPE_CHOICES, blank=True, null=True)
    pain_location = models.CharField(max_length=20, choices=PAIN_LOCATION_CHOICES, blank=True, null=True)
    pain_duration = models.CharField(max_length=20, choices=PAIN_DURATION_CHOICES, blank=True, null=True)
    treated_before = models.BooleanField(default=False)
    physician_notes = models.TextField(blank=True, null=True)
    photos = models.ImageField(upload_to='cases/photos/', blank=True, null=True, validators=[validate_medical_image])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cases'
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Case {self.title or self.id} for {self.patient.username}"
