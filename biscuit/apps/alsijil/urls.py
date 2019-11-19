from django.urls import path

from . import views


urlpatterns = [
    path('lesson', views.lesson, name='lesson'),
    path('lesson/<int:year>/<int:week>/<int:period_id>', views.lesson,
         name='lesson_by_week_and_period'),
    path('week', views.week_view, name='week_view'),
    path('week/<int:year>/<int:week>', views.week_view,
         name='week_view_by_week'),
    path('print/group/<int:id_>', views.full_register_group,
         name='full_register_group'),
    path('absence/new', views.register_absence,
         name='register_absence'),
]
