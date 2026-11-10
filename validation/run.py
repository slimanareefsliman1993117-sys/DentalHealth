import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['DJANGO_SETTINGS_MODULE']='validation.settings'
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
