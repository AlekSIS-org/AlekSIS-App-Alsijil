from django.urls import path

from . import views


urlpatterns = [
    path('lesson', views.lesson, name='lesson'),
]
