from .settings import *          # importa tutto
CSRF_COOKIE_SECURE   = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT  = False
# IP pubblico da cui stai provando
CSRF_TRUSTED_ORIGINS = ["http://80.211.4.179:8000"]
