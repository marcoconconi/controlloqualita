# cq_project/urls.py

from django.contrib import admin
from django.urls import path, include
from two_factor.admin import AdminSiteOTPRequired

from django.contrib.auth import views as auth_views


# patch 2FA anche sull’admin
admin.autodiscover()
admin.site.__class__ = AdminSiteOTPRequired

urlpatterns = [
    #    prefisso rimosso: ora sarà /account/login/ ecc.
    path('', include(('two_factor.urls', 'two_factor'), namespace='two_factor')),

    path('controlloqualita/', include(('controlloqualita.urls',
                                       'controlloqualita'),
                                       namespace='controlloqualita')),
    path('admin/', admin.site.urls),
    
    path(
        "account/password/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="/account/password/done/",
        ),
        name="password_change",
    ),
    path(
        "account/password/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),    
    
    
    
]