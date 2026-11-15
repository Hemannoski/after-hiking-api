import logging
from typing import cast

from django.db import transaction
from django.db.models import F, Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from randonnees.models import Randonnee, StatistiqueRandonnee, StatutRandonnee

from .models import Media, StatutTraitementDuMedia, TypeMedias
from .serializers import (
    AutorisationMediaSerializer,
    ChoisirCouvertureSerializer,
    EnregistrerMediaSerializer,
    MediaSerializer,
    ReordonnerMediasSerializer,
)
from .utils import (
    dossier_cloudinary,
    generer_signature_upload_cloudinary,
    supprimer_fichier_cloudinary,
    verifier_ressource_cloudinary,
)

logger = logging.getLogger(__name__)


def randonnee_visible_ou_404(pk, utilisateur):
    randonnee = get_object_or_404(Randonnee, pk=pk)
    if randonnee.status_randonnee != StatutRandonnee.PUBLIE and randonnee.auteur.pk != utilisateur.pk:
        raise Http404
    return randonnee


def randonnee_de_l_auteur_ou_404(pk, utilisateur):
    return get_object_or_404(Randonnee, pk=pk, auteur=utilisateur)


def synchroniser_video_si_prete(media):
    """
    Vérifie auprès de Cloudinary si une vidéo en attente est désormais prête.
    Appelé lors de la consultation de la galerie ou du statut d'un média.
    """
    if (
        media.type_media != TypeMedias.VIDEO
        or media.status_traitement != StatutTraitementDuMedia.EN_ATTENTE
    ):
        return

    ressource = verifier_ressource_cloudinary(
        media.public_id,
        resource_type="video",
    )
    if (
        ressource is not None
        and ressource.get("duration") is not None
    ):
        media.status_traitement = StatutTraitementDuMedia.PRET
        media.duree_video_en_seconde = float(ressource["duration"])
        if ressource.get("secure_url"):
            media.url_media = ressource["secure_url"]
        media.save(
            update_fields=[
                "status_traitement",
                "duree_video_en_seconde",
                "url_media",
            ]
        )


class AutoriserMediaView(APIView):
    """POST /randonnees/{id}/medias/autorisation"""

    def post(self, request, pk):
        randonnee = randonnee_de_l_auteur_ou_404(pk, request.user)

        serializer = AutorisationMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees_validees = cast(dict[str, str], serializer.validated_data)
        type_media = donnees_validees['type_media']

        resource_type = 'video' if type_media == TypeMedias.VIDEO else 'image'
        return Response(
            generer_signature_upload_cloudinary(request.user.pk, randonnee.pk, resource_type)
        )


class MediaListCreateView(APIView):
    """GET et POST /randonnees/{id}/medias — une seule route, deux méthodes."""

    def get(self, request, pk):
        randonnee = randonnee_visible_ou_404(pk, request.user)

        medias = (
            Media.objects
            .filter(randonnee=randonnee)
            .select_related('randonnee')
            .order_by('ordre', '-id')
        )
        nb_photos = medias.filter(type_media=TypeMedias.PHOTO).count()
        nb_videos = medias.filter(type_media=TypeMedias.VIDEO).count()

        filtre = request.query_params.get('type')
        if filtre in (TypeMedias.PHOTO, TypeMedias.VIDEO):
            medias = medias.filter(type_media=filtre)

        # Correction : on synchronise les vidéos en attente, limitées à 5 pour éviter la latence
        videos_en_attente = medias.filter(
            type_media=TypeMedias.VIDEO,
            status_traitement=StatutTraitementDuMedia.EN_ATTENTE,
        )[:5]
        for media in videos_en_attente:
            synchroniser_video_si_prete(media)

        # Correction : on recharge le queryset après synchronisation
        # pour garantir que les objets sérialisés ont les dernières valeurs
        medias = (
            Media.objects
            .filter(randonnee=randonnee)
            .select_related('randonnee')
            .order_by('ordre', '-id')
        )
        if filtre in (TypeMedias.PHOTO, TypeMedias.VIDEO):
            medias = medias.filter(type_media=filtre)

        return Response({
            'totaux': {'tout': nb_photos + nb_videos, 'photos': nb_photos, 'videos': nb_videos},
            'media_couverture_id': getattr(randonnee, 'media_couverture_id', None),
            'medias': MediaSerializer(medias, many=True).data,
        })

    def post(self, request, pk):
        serializer = EnregistrerMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = cast(dict[str, object], serializer.validated_data)

        with transaction.atomic():
            randonnee = get_object_or_404(
                Randonnee.objects.select_for_update(), pk=pk, auteur=request.user
            )

            prefixe = dossier_cloudinary(request.user.pk, randonnee.pk) + '/'
            if not cast(str, donnees['public_id']).startswith(prefixe):
                return Response(
                    {'public_id': "Ce fichier n'appartient pas au dossier de cette randonnée."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ressource = verifier_ressource_cloudinary(
                cast(str, donnees['public_id']), resource_type="auto"
            )
            if ressource is None:
                return Response(
                    {'public_id': "Ce fichier n'existe pas sur Cloudinary."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            type_reel = ressource.get('resource_type', '').lower()
            type_media = TypeMedias.PHOTO if type_reel == 'image' else TypeMedias.VIDEO

            dernier_ordre = Media.objects.filter(randonnee=randonnee).aggregate(
                maximum=Max('ordre')
            )['maximum'] or 0

            # Une vidéo est PRET si Cloudinary fournit déjà la durée
            if type_media == TypeMedias.PHOTO or ressource.get("duration") is not None:
                statut = StatutTraitementDuMedia.PRET
            else:
                statut = StatutTraitementDuMedia.EN_ATTENTE

            media = Media.objects.create(
                randonnee=randonnee,
                ordre=dernier_ordre + 1,
                type_media=type_media,
                status_traitement=statut,
                public_id=donnees['public_id'],
                url_media=ressource.get('secure_url', donnees['url_media']),
                taille_en_octet=ressource.get('bytes', donnees['taille_en_octet']),
                duree_video_en_seconde=(
                    float(ressource["duration"])
                    if (
                        type_media == TypeMedias.VIDEO
                        and ressource.get("duration") is not None
                    )
                    else None
                ),
            )

            # Incrémenter le compteur de médias dans StatistiqueRandonnee
            StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                nombre_medias=F('nombre_medias') + 1
            )

            if randonnee.media_couverture is None:
                randonnee.media_couverture = media
                randonnee.save(update_fields=['media_couverture'])

        return Response(MediaSerializer(media).data, status=status.HTTP_201_CREATED)


class ChoisirCouvertureView(APIView):
    """PUT /randonnees/{id}/media_couverture — photo ou vidéo acceptées."""

    def put(self, request, pk):
        randonnee = randonnee_de_l_auteur_ou_404(pk, request.user)

        serializer = ChoisirCouvertureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees_validees = cast(dict[str, int], serializer.validated_data)

        media = get_object_or_404(
            Media, pk=donnees_validees['media_id'], randonnee=randonnee
        )

        randonnee.media_couverture = media
        randonnee.save(update_fields=['media_couverture'])

        return Response({'media_couverture_id': media.pk})


class StatutMediaView(APIView):
    """GET /medias/{id}/statut — réutilise synchroniser_video_si_prete() pour une seule source de vérité."""

    def get(self, request, pk):
        media = get_object_or_404(Media.objects.select_related('randonnee'), pk=pk)
        randonnee_visible_ou_404(media.randonnee.pk, request.user)

        synchroniser_video_si_prete(media)
        media.refresh_from_db()

        return Response({
            'id': media.pk,
            'type_media': media.type_media,
            'status_traitement': media.status_traitement,
            'url_media': media.url_media,
        })


class ReordonnerMediasView(APIView):
    """PATCH /randonnees/{id}/medias/ordre"""

    def patch(self, request, pk):
        randonnee = randonnee_de_l_auteur_ou_404(pk, request.user)

        serializer = ReordonnerMediasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        donnees_validees = cast(
            dict[str, list[dict[str, int]]], serializer.validated_data
        )
        ordres = donnees_validees['ordres']
        identifiants = {item['id'] for item in ordres}
        autorises = set(
            Media.objects.filter(randonnee=randonnee, pk__in=identifiants)
            .values_list('pk', flat=True)
        )
        if autorises != identifiants:
            return Response(
                {'ordres': "Un média de la liste n'appartient pas à cette randonnée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in ordres:
                Media.objects.filter(pk=item['id']).update(ordre=item['ordre'])

        return Response({'detail': "Ordre mis à jour."})


class SupprimerMediaView(APIView):
    """DELETE /medias/{id} — supprime la ligne et le fichier distant via on_commit."""

    def delete(self, request, pk):
        media = get_object_or_404(Media.objects.select_related('randonnee'), pk=pk)
        randonnee = randonnee_de_l_auteur_ou_404(media.randonnee.pk, request.user)

        public_id = media.public_id
        resource_type = 'video' if media.type_media == TypeMedias.VIDEO else 'image'

        with transaction.atomic():
            if randonnee.media_couverture == media:
                suivant = (
                    Media.objects.filter(randonnee=randonnee)
                    .exclude(pk=media.pk)
                    .order_by('ordre', '-id')
                    .first()
                )
                randonnee.media_couverture = suivant
                randonnee.save(update_fields=['media_couverture'])

            media.delete()

            # Décrémenter le compteur de médias dans StatistiqueRandonnee
            from randonnees.models import StatistiqueRandonnee
            StatistiqueRandonnee.objects.filter(randonnee=randonnee).update(
                nombre_medias=F('nombre_medias') - 1
            )

            transaction.on_commit(
                lambda: supprimer_fichier_cloudinary(public_id, resource_type)
            )

        return Response(status=status.HTTP_204_NO_CONTENT)