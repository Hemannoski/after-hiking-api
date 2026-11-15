import logging
from typing import cast

from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import Utilisateur
from randonnees.models import Randonnee, StatistiqueRandonnee, StatutRandonnee

from .models import Commentaire, Like
from .serializers import CommentaireSerializer, CreerCommentaireSerializer

logger = logging.getLogger(__name__)


def _randonnee_visible_ou_404(pk: int, utilisateur: Utilisateur) -> Randonnee:
    """Brouillon et masqué : auteur seulement. Published : tout utilisateur connecté."""
    randonnee = get_object_or_404(Randonnee, pk=pk)
    if randonnee.status_randonnee != StatutRandonnee.PUBLIE and randonnee.auteur.pk != utilisateur.pk:
        raise Http404
    return randonnee


class LikeView(APIView):
    """
    POST  /randonnees/{id}/like    -> Aimer une randonnée.
    DELETE /randonnees/{id}/like   -> Retirer son like.
    
    Met à jour atomiquement le compteur StatistiqueRandonnee.nombre_likes.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):

        randonnee = _randonnee_visible_ou_404(pk, cast(Utilisateur, request.user))

        with transaction.atomic():

            _like, created = Like.objects.get_or_create(
                auteur=request.user,
                randonnee=randonnee,
            )

            if created:
                # Incrémentation atomique du compteur
                StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                    nombre_likes=F('nombre_likes') + 1
                )

                # Notification à l'auteur de la randonnée (si ce n'est pas lui-même)
                if randonnee.auteur.pk != request.user.pk:
                    self._declencher_notification_like(randonnee, request.user)

        return Response(
            {'detail': "Randonnée likée.", 'a_jaime': True},
            status=status.HTTP_200_OK,
        )
    

    def delete(self, request, pk: int):


        randonnee = _randonnee_visible_ou_404(pk, cast(Utilisateur, request.user))

        with transaction.atomic():
            deleted, _ = Like.objects.filter(
                auteur=request.user,
                randonnee=randonnee,
            ).delete()

            if deleted:
                # Décrémentation atomique du compteur
                StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                    nombre_likes=F('nombre_likes') - 1
                )

        return Response(
            {'detail': "Like retiré.", 'a_jaime': False},
            status=status.HTTP_200_OK,
        )


    def _declencher_notification_like(self, randonnee: Randonnee, auteur: Utilisateur):
        """Envoie une notification de type 'like' à l'auteur de la randonnée."""
        from notifications.models import Notification, TypeNotification

        Notification.objects.create(
            destinataire=randonnee.auteur,
            declencheur=auteur,
            randonnee=randonnee,
            type_notification=TypeNotification.LIKE,
        )


class CommentaireListCreateView(ListCreateAPIView):
    """
    GET  /randonnees/{id}/commentaires -> Liste paginée des commentaires.
    POST /randonnees/{id}/commentaires -> Ajouter un commentaire.
    
    Met à jour atomiquement le compteur StatistiqueRandonnee.nombre_commentaires.
    """

    permission_classes = [IsAuthenticated]
    serializer_class: type[CommentaireSerializer] = CommentaireSerializer
    create_serializer_class: type[CreerCommentaireSerializer] = CreerCommentaireSerializer

    def get_randonnee(self):

        return _randonnee_visible_ou_404(
            self.kwargs['pk'], cast(Utilisateur, self.request.user)
        )

    def get_queryset(self): #type: ignore
        
        return (
            Commentaire.objects
            .filter(randonnee=self.get_randonnee())
            .select_related('commentateur')
            .order_by('-date_creation_commentaire')
        )

    def get_serializer_class(self): #type: ignore
        if self.request.method == 'POST':
            return self.create_serializer_class
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        randonnee = self.get_randonnee()

        serializer = CreerCommentaireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            commentaire = serializer.save(
                commentateur=request.user,
                randonnee=randonnee,
            )

            # ncrémentation atomique du compteur
            StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                nombre_commentaires=F('nombre_commentaires') + 1
            )

            # Notification à l'auteur de la randonnée (si ce n'est pas lui-même)
            if randonnee.auteur.pk != request.user.pk:
                self._declencher_notification_commentaire(randonnee, request.user)

        response_serializer = CommentaireSerializer(commentaire, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def _declencher_notification_commentaire(self, randonnee: Randonnee, auteur: Utilisateur):
        """Envoie une notification de type 'commentaire' à l'auteur de la randonnée."""
        from notifications.models import Notification, TypeNotification

        Notification.objects.create(
            destinataire=randonnee.auteur,
            declencheur=auteur,
            randonnee=randonnee,
            type_notification=TypeNotification.COMMENTAIRE,
        )


class CommentaireDetailView(APIView):
    """
    DELETE /commentaires/{id} -> Supprimer son commentaire.
    
    Décrémenter atomiquement le compteur StatistiqueRandonnee.nombre_commentaires.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk: int):
        commentaire = get_object_or_404(
            Commentaire.objects.select_related('randonnee'),
            pk=pk,
        )

        # L'auteur du commentaire ou l'auteur de la randonnée peuvent le supprimer
        if (
            commentaire.commentateur.pk != request.user.pk
            and commentaire.randonnee.auteur_id != request.user.pk
        ):
            return Response(
                {'detail': "Vous n'êtes pas autorisé à supprimer ce commentaire."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            randonnee = commentaire.randonnee
            commentaire.delete()

            # Décrémentation atomique du compteur
            StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                nombre_commentaires=F('nombre_commentaires') - 1
            )

        return Response(
            {'detail': "Commentaire supprimé avec succès."},
            status=status.HTTP_204_NO_CONTENT,
        )