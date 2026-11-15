from django.urls import path

from .views import (
    MarquerToutesNotificationsLuesView,
    MarquerUneNotificationLueView,
    NombreNotificationsNonLuesView,
    NotificationListView,
)

urlpatterns = [
    path('notifications', NotificationListView.as_view(), name='notification-liste'),
    path('notifications/non-lues/nombre', NombreNotificationsNonLuesView.as_view(), name='notification-compte-non-lues'),
    path('notifications/lues', MarquerToutesNotificationsLuesView.as_view(), name='notification-marquer-toutes-lues'),
    path('notifications/<int:pk>/lue', MarquerUneNotificationLueView.as_view(), name='notification-marquer-une-lue'),
]