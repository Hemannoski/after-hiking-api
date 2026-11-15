from django.urls import path

from .views import (
    AppareilDetailView,
    AppareilView,
    FirebaseLoginView,
    MoiView,
    PhotoProfilView,
    ProfilUtilisateurView,
    RechercheUtilisateursView,
    UtilisateurRandonneesView,
)

urlpatterns = [
    path('auth/firebase', FirebaseLoginView.as_view(), name='auth-firebase'),
    path('moi/photo', PhotoProfilView.as_view(), name='moi-photo'),
    path('moi', MoiView.as_view(), name='moi'),
    path('utilisateurs/<int:pk>', ProfilUtilisateurView.as_view(), name='utilisateur-profil'),
    path('recherche/utilisateurs', RechercheUtilisateursView.as_view(), name='recherche-utilisateurs'),
    path('utilisateurs/<int:pk>/randonnees', UtilisateurRandonneesView.as_view(), name='utilisateur-randonnees'),
    # Nouvelles routes pour les appareils
    path('appareils', AppareilView.as_view(), name='appareils'),
    path('appareils/<int:id>', AppareilDetailView.as_view(), name='appareil-detail'),
]