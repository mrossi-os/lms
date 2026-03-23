__version__ = "0.0.1"

# Monkey-patch SMTPServer.session property
import os_lms.overrides.smtp  # noqa: F401
