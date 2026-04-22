from django.urls import path
from .views import (
    UnitListView, UnitCreateView,
    QuestionListView, QuestionCreateView,
    QuestionUpdateView, QuestionDeleteView,
    QuestionImportView,
)

urlpatterns = [
    # Unit
    path('admin/info/units/', UnitListView.as_view(), name='info-units-list'),
    path('admin/info/units/create/', UnitCreateView.as_view(), name='info-units-create'),

    # Question CRUD
    path('admin/info/questions/', QuestionListView.as_view(), name='info-questions-list'),
    path('admin/info/questions/create/', QuestionCreateView.as_view(), name='info-questions-create'),
    path('admin/info/questions/<int:pk>/', QuestionUpdateView.as_view(), name='info-questions-update'),
    path('admin/info/questions/<int:pk>/delete/', QuestionDeleteView.as_view(), name='info-questions-delete'),

    # Bulk import
    path('admin/info/questions/import/', QuestionImportView.as_view(), name='info-questions-import'),
]
