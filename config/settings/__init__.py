"""
Django settings module loader.

Loads the appropriate settings module based on DJANGO_ENV environment variable.
Defaults to development settings.
"""

import os

# Determine which settings to use based on DJANGO_ENV
env = os.getenv("DJANGO_ENV", "development")

if env == "production":
    from .production import *
elif env == "test":
    from .test import *
else:
    from .development import *
