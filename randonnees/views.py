import logging
from typing import cast

from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import Utilisateur

from .models import (
    DifficulteRandonnee,
    Randonnee,
    StatistiqueRandonnee,
    StatutRandonnee,
)
from .serializers import (
    RandonneeCreateSerializer,
    RandonneeDetailSerializer,
    RandonneeFilSerializer,
    RandonneeListeSerializer,
    RandonneeRechercheSerializer,
    RandonneeUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _randonnee_visible_ou_404(pk: int, utilisateur: Utilisateur) -> Randonnee:
    """Récupère la randonnée avec ses statistiques et son média de couverture préchargés."""
    randonnee = get_object_or_404(
        Randonnee.objects.select_related('statistiques', 'media_couverture'),
        pk=pk
    )
    if (
        randonnee.status_randonnee != StatutRandonnee.PUBLIE
        and getattr(randonnee, 'auteur_id', None) != utilisateur.pk
    ):
        raise Http404
    return randonnee


def _randonnee_de_l_auteur_ou_404(pk: int, utilisateur: Utilisateur) -> Randonnee:
    return get_object_or_404(
        Randonnee.objects.select_related('statistiques', 'media_couverture'),
        pk=pk,
        auteur=utilisateur
    )


class RandonneeView(APIView):
    """
    GET /randonnees/{id}    -> Détail complet (avec incrémentation des vues).
    PATCH /randonnees/{id}  -> Modifier ma randonnée (brouillon uniquement).
    DELETE /randonnees/{id} -> Supprimer ma randonnée.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        randonnee = _randonnee_visible_ou_404(pk, request.user)

        # Incrémentation atomique du nombre de vues si la randonnée est publiée
        if randonnee.status_randonnee == StatutRandonnee.PUBLIE:
            StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                nombre_vues=F('nombre_vues') + 1
            )
            stats = getattr(randonnee, 'statistiques', None)
            if stats is not None:
                stats.refresh_from_db(fields=['nombre_vues'])

        serializer = RandonneeDetailSerializer(randonnee, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk: int):
        randonnee = _randonnee_de_l_auteur_ou_404(pk, request.user)

        if randonnee.status_randonnee == StatutRandonnee.PUBLIE:
            return Response(
                {'detail': "Une randonnée publiée ne peut plus être modifiée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RandonneeUpdateSerializer(randonnee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            randonnee_modifiee = cast(Randonnee, serializer.save())

            # Mettre à jour la longueur de description pour l'IA
            validated_data = cast(dict[str, object], serializer.validated_data)
            if 'description_randonnee' in validated_data:
                stats, _ = StatistiqueRandonnee.objects.get_or_create(randonnee=randonnee_modifiee)
                stats.longueur_description_randonnee = len(randonnee_modifiee.description_randonnee)
                stats.save(update_fields=['longueur_description_randonnee'])

        return Response(
            RandonneeDetailSerializer(randonnee_modifiee, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk: int):
        randonnee = _randonnee_de_l_auteur_ou_404(pk, request.user)

        with transaction.atomic():
            randonnee.delete()

        return Response(
            {'detail': "Randonnée supprimée avec succès."},
            status=status.HTTP_204_NO_CONTENT,
        )


class RandonneeCreateView(APIView):
    """POST /randonnees : Créer une randonnée en brouillon."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RandonneeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            randonnee = cast(Randonnee, serializer.save(auteur=request.user))
            
            # Fiche statistique initialisée avec la longueur de description
            StatistiqueRandonnee.objects.get_or_create(
                randonnee=randonnee,
                defaults={'longueur_description_randonnee': len(randonnee.description_randonnee)}
            )

        return Response(
            RandonneeDetailSerializer(randonnee, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class PublierRandonneeView(APIView):
    """
    POST /randonnees/{id}/publier : Passer une randonnée de brouillon à publié.
    Déclenche une notification à tous les utilisateurs actifs.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        randonnee = _randonnee_de_l_auteur_ou_404(pk, request.user)

        if randonnee.status_randonnee != StatutRandonnee.BROUILLON:
            return Response(
                {'detail': "Cette randonnée n'est pas en brouillon."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            randonnee.status_randonnee = StatutRandonnee.PUBLIE
            randonnee.date_publication_randonnee = timezone.now()
            randonnee.save(update_fields=['status_randonnee', 'date_publication_randonnee'])

            StatistiqueRandonnee.objects.get_or_create(randonnee=randonnee)

            # Envoi des notifications en masse
            self._declencher_notifications(randonnee, request.user)

        return Response(
            RandonneeDetailSerializer(randonnee, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    def _declencher_notifications(self, randonnee: Randonnee, auteur: Utilisateur):
        """Notification envoyée à tous les utilisateurs actifs."""
        from notifications.models import Notification, TypeNotification

        autres_utilisateurs = Utilisateur.objects.filter(
            is_active=True,
            date_suppression__isnull=True
        ).exclude(pk=auteur.pk)

        notifications = [
            Notification(
                destinataire=dest,
                declencheur=auteur,
                randonnee=randonnee,
                type_notification=TypeNotification.NOUVELLE_RANDONNEE,
            )
            for dest in autres_utilisateurs
        ]
        Notification.objects.bulk_create(notifications)


class ListeBrouillonsView(ListAPIView):
    """GET /moi/brouillons : Liste des brouillons de l'utilisateur connecté."""

    permission_classes = [IsAuthenticated]
    serializer_class = RandonneeListeSerializer

    def get_queryset(self) -> QuerySet[Randonnee]:  # type: ignore[override]
        return (
            Randonnee.objects
            .filter(auteur=self.request.user, status_randonnee=StatutRandonnee.BROUILLON)
            .order_by('-id')
        )



class FilView(ListAPIView):
    """
    GET /fil : Fil principal des randonnées publiées (paginé par 20).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RandonneeFilSerializer

    def get_queryset(self):#type: ignore[override]
        return (
            Randonnee.objects
            .filter(status_randonnee=StatutRandonnee.PUBLIE)
            .select_related('auteur', 'media_couverture', 'statistiques')
            .order_by('-date_publication_randonnee')
        )


class RechercheRandonneesView(ListAPIView):
    """
    GET /recherche/randonnees : Recherche de randonnées par mot-clé, lieu, difficulté, durée.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RandonneeRechercheSerializer

    def get_queryset(self):#type: ignore[override]
        request = cast(Request, self.request)
        queryset = (
            Randonnee.objects
            .filter(status_randonnee=StatutRandonnee.PUBLIE)
            .select_related('auteur', 'media_couverture')
        )

        q = request.query_params.get('q', '').strip()[:100]
        if q:
            queryset = queryset.filter(
                Q(titre_randonnee__icontains=q) |
                Q(description_randonnee__icontains=q) |
                Q(lieu_randonnee__icontains=q)
            )

        lieu = request.query_params.get('lieu', '').strip()[:255]
        if lieu:
            queryset = queryset.filter(lieu_randonnee__icontains=lieu)

        difficulte = request.query_params.get('difficulte', '').strip()
        if difficulte in dict(DifficulteRandonnee.choices):
            queryset = queryset.filter(niveau_difficulte_randonnee=difficulte)

        duree_min = request.query_params.get('duree_min')
        if duree_min:
            try:
                queryset = queryset.filter(duree_randonnee_minutes__gte=int(duree_min))
            except ValueError:
                pass

        duree_max = request.query_params.get('duree_max')
        if duree_max:
            try:
                queryset = queryset.filter(duree_randonnee_minutes__lte=int(duree_max))
            except ValueError:
                pass

        return queryset.order_by('-date_publication_randonnee')