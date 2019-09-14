from django.urls import path

from . import views


urlpatterns = [
    path('lesson', views.lesson, name='lesson'),
    path('lesson/<int:year>/<int:week>/<int:period_id>', views.lesson,
         name='lesson_by_week_and_period'),
    path('group/week', views.group_week, name='group_week'),
    path('group/week/<int:year>/<int:week>', views.group_week,
         name='group_week_by_week'),
]
