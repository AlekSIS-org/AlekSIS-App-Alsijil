from django.urls import path

from . import views


urlpatterns = [
    path('lesson', views.lesson, name='lesson'),
    path('lesson/<int:year>/<int:week>/<int:period_id>', views.lesson,
         name='lesson_by_week_and_period'),
    path('group/week', views.week_view, name='week_view'),
    path('group/week/<int:year>/<int:week>', views.week_view,
         name='week_view_by_week'),
    path('print/group/<int:id_>', views.full_register_group,
        name='full_register_group')
]
