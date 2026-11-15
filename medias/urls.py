from django.urls import path

from .views import (
    AutoriserMediaView,
    ChoisirCouvertureView,
    MediaListCreateView,
    ReordonnerMediasView,
    StatutMediaView,
    SupprimerMediaView,
)

urlpatterns = [
    path('randonnees/<int:pk>/medias/autorisation', AutoriserMediaView.as_view(), name='media-autorisation'),
    path('randonnees/<int:pk>/medias', MediaListCreateView.as_view(), name='media-list-create'),
    path('randonnees/<int:pk>/media_couverture', ChoisirCouvertureView.as_view(), name='media-couverture'),
    path('randonnees/<int:pk>/medias/ordre', ReordonnerMediasView.as_view(), name='media-reordonner'),
    path('medias/<int:pk>/statut', StatutMediaView.as_view(), name='media-statut'),
    path('medias/<int:pk>', SupprimerMediaView.as_view(), name='media-supprimer'),
]