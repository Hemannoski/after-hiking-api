from django.urls import path

from .views import CommentaireDetailView, CommentaireListCreateView, LikeView

urlpatterns = [
    path('randonnees/<int:pk>/like', LikeView.as_view(), name='like-randonnee'),
    path('randonnees/<int:pk>/commentaires', CommentaireListCreateView.as_view(), name='commentaire-liste'),
    path('commentaires/<int:pk>', CommentaireDetailView.as_view(), name='commentaire-detail'),
]