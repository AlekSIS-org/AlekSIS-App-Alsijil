from django.urls import path

from . import views


urlpatterns = [
    path('lesson', views.lesson, name='lesson'),
    path('lesson/<int:week>/<int:period_id>', views.lesson,
         name='lesson_by_week_and_period'),
]
