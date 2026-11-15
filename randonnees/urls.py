from django.urls import path

from .views import (
    FilView,
    ListeBrouillonsView,
    PublierRandonneeView,
    RandonneeCreateView,
    RandonneeView,
    RechercheRandonneesView,
)

urlpatterns = [
    path('randonnees', RandonneeCreateView.as_view(), name='randonnee-creer'),
    path('randonnees/<int:pk>', RandonneeView.as_view(), name='randonnee-detail'),
    path('randonnees/<int:pk>/publier', PublierRandonneeView.as_view(), name='randonnee-publier'),
    path('moi/brouillons', ListeBrouillonsView.as_view(), name='brouillons-liste'),
    path('fil', FilView.as_view(), name='fil-principal'),
    path('recherche/randonnees', RechercheRandonneesView.as_view(), name='recherche-randonnees'),
]