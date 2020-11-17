from django.urls import path

from . import views

urlpatterns = [
    path("lesson", views.lesson, name="lesson"),
    path(
        "lesson/<int:year>/<int:week>/<int:period_id>",
        views.lesson,
        name="lesson_by_week_and_period",
    ),
    path("week/", views.week_view, name="week_view"),
    path("week/<int:year>/<int:week>/", views.week_view, name="week_view_by_week"),
    path("week/year/cw/", views.week_view, name="week_view_placeholders"),
    path("week/<str:type_>/<int:id_>/", views.week_view, name="week_view"),
    path("week/year/cw/<str:type_>/<int:id_>/", views.week_view, name="week_view_placeholders",),
    path(
        "week/<int:year>/<int:week>/<str:type_>/<int:id_>/",
        views.week_view,
        name="week_view_by_week",
    ),
    path("print/group/<int:id_>", views.full_register_group, name="full_register_group"),
    path("groups/", views.my_groups, name="my_groups"),
    path("groups/<int:pk>/", views.StudentsList.as_view(), name="students_list"),
    path("persons/", views.my_students, name="my_students"),
    path("persons/<int:id_>/", views.overview_person, name="overview_person"),
    path("me/", views.overview_person, name="overview_me"),
    path(
        "notes/<int:pk>/delete/",
        views.DeletePersonalNoteView.as_view(),
        name="delete_personal_note",
    ),
    path("absence/new/<int:id_>/", views.register_absence, name="register_absence"),
    path("extra_marks/", views.ExtraMarkListView.as_view(), name="extra_marks"),
    path("extra_marks/create/", views.ExtraMarkCreateView.as_view(), name="create_extra_mark",),
    path("extra_marks/<int:pk>/edit/", views.ExtraMarkEditView.as_view(), name="edit_extra_mark",),
    path(
        "extra_marks/<int:pk>/delete/",
        views.ExtraMarkDeleteView.as_view(),
        name="delete_extra_mark",
    ),
    path("excuse_types/", views.ExcuseTypeListView.as_view(), name="excuse_types"),
    path("excuse_types/create/", views.ExcuseTypeCreateView.as_view(), name="create_excuse_type",),
    path(
        "excuse_types/<int:pk>/edit/", views.ExcuseTypeEditView.as_view(), name="edit_excuse_type",
    ),
    path(
        "excuse_types/<int:pk>/delete/",
        views.ExcuseTypeDeleteView.as_view(),
        name="delete_excuse_type",
    ),
]
