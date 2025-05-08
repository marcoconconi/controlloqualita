app_name = 'controlloqualita'

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import RedirectView
from django.urls import reverse_lazy

urlpatterns = [
    path('',           views.dashboard,   name='dashboard'),
    path('upload/',    views.upload_csv,  name='upload_csv'),
    path('upload_ok/', views.upload_ok,   name='upload_ok'),
    path('set-esiti/', views.set_esiti,   name='set_esiti'),
    path('delete_filtered/', views.delete_filtered,  name='delete_filtered'),
         
    path(
        "logout/",
        RedirectView.as_view(url=reverse_lazy("two_factor:logout")),
        name="logout"  # ← resta utilizzabile nei vecchi template
    ),
]
