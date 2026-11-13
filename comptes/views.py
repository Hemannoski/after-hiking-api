from django.db import IntegrityError, transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView
from rest_framework.request import Request
from typing import Any, cast
import logging

from .firebase import verifier_jeton_firebase, supprimer_compte_firebase
from firebase_admin.exceptions import FirebaseError
from .stockage import StockageIndisponible, envoyer_photo_profil, supprimer_photo_profil
from .models import Utilisateur
from .serializers import (
    InscriptionSerializer, UtilisateurSerializer, ModifierProfilSerializer, 
    ProfilPublicSerializer, ProfilPublicSerializer, PhotoProfilSerializer)

from .utils import choisir_nom_utilisateur, generer_nom_utilisateur

from rest_framework.parsers import MultiPartParser

from django.db.models import Count, Q, QuerySet

from randonnees.models import StatutRandonnee


logger = logging.getLogger(__name__)

class FirebaseLoginView(APIView):
    """POST /auth/firebase : connexion ou inscription (premier appel)."""

    authentication_classes = []
    permission_classes = [AllowAny]
 
    def get_authenticate_header(self, request):
        return 'Bearer'  # pour répondre 401 et non 403

    def post(self, request):
        # 1. Vérifier le jeton
        decoded = verifier_jeton_firebase(request, verifier_revocation=True)

        if decoded is None:
            raise NotAuthenticated("Jeton Firebase manquant.")
        
        firebase_uid = decoded['uid']

        email = decoded.get('email')

        contexte = {'request': request}

        # 2. Connexion : l'utilisateur existe déjà
        utilisateur = Utilisateur.objects.filter(firebase_uid=firebase_uid).first()

        if utilisateur is not None:
            if not utilisateur.is_active or utilisateur.date_suppression is not None:
                return Response({'detail': "Ce compte est désactivé ou supprimé."}, status=status.HTTP_403_FORBIDDEN)
            
            return Response(UtilisateurSerializer(utilisateur, context=contexte).data, status=status.HTTP_200_OK)


        # 3. Inscription : contrôles avant de créer
        if not email:
            return Response({'detail': "Le jeton ne contient pas d'email."}, status=status.HTTP_400_BAD_REQUEST)
        
        if Utilisateur.objects.filter(email__iexact=email).exists():
            return Response({'detail': "Cet email est déjà utilisé par un autre compte."}, status=status.HTTP_409_CONFLICT)

        serializer = InscriptionSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        donnees: dict[str, Any] = dict(cast(dict[str, Any], serializer.validated_data))

        propose = donnees.pop('nom_utilisateur', None)

        # 4. Création, avec nouvel essai si le nom d'utilisateur est pris entre-temps
        nom_utilisateur = choisir_nom_utilisateur(propose, donnees['nom_complet'], email)

        for _ in range(3):
            try:
                with transaction.atomic():
                    utilisateur = Utilisateur.objects.create_user(
                        email=email,
                        firebase_uid=firebase_uid,
                        nom_utilisateur=nom_utilisateur,
                        **donnees,
                    )
                break

            except IntegrityError:
                # Deux requêtes simultanées pour le même compte : on renvoie l'existant
                existant = Utilisateur.objects.filter(firebase_uid=firebase_uid).first()

                if existant is not None:
                    return Response(UtilisateurSerializer(existant, context=contexte).data, status=status.HTTP_200_OK)
                
                nom_utilisateur = generer_nom_utilisateur(donnees['nom_complet'], email)
        else:
            return Response({'detail': "Création du compte impossible, réessayez."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(UtilisateurSerializer(utilisateur, context=contexte).data, status=status.HTTP_201_CREATED)


class PhotoProfilView(APIView):
    """POST /moi/photo : choisir ou changer sa photo de profil."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        utilisateur = cast(Utilisateur, request.user)

        serializer = PhotoProfilSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = cast(dict[str, Any], serializer.validated_data)['photo']

        try:
            url = envoyer_photo_profil(photo, utilisateur)
        except StockageIndisponible:
            return Response(
                {'detail': "Le service d'hébergement des images est indisponible, réessayez."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        utilisateur.photo_profil = url
        utilisateur.save(update_fields=['photo_profil'])
        return Response(
            UtilisateurSerializer(utilisateur, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )


class MoiView(generics.RetrieveUpdateDestroyAPIView):
    """GET /moi : mon profil. PATCH /moi : modifier mon profil."""

    http_method_names = ['get', 'patch', 'delete', 'options']

    def get_object(self) -> Utilisateur:  # type: ignore[override]
        return cast(Utilisateur, self.request.user)

    def get_serializer_class(self) -> type[Serializer]:  # type: ignore[override]
        if self.request.method == 'PATCH':
            return ModifierProfilSerializer
        return UtilisateurSerializer

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)  # valide et enregistre
        return Response(
            UtilisateurSerializer(self.get_object(), context=self.get_serializer_context()).data
        )


    def destroy(self, request, *args, **kwargs):
        utilisateur = cast(Utilisateur, request.user)
        # Django remet pk à None après delete() : on garde ce dont on a besoin avant
        utilisateur_id = utilisateur.pk
        firebase_uid = utilisateur.firebase_uid

        try:
            with transaction.atomic():
                utilisateur.delete()  # la cascade supprime ses données
                supprimer_compte_firebase(firebase_uid)  # si ça échoue, la base est restaurée
        except (FirebaseError, ValueError):
            logger.exception("Échec de la suppression du compte (utilisateur %s)", utilisateur_id)
            return Response(
                {'detail': "Suppression impossible pour le moment, réessayez."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        supprimer_photo_profil(utilisateur_id)  # tolère l'échec : le compte n'existe déjà plus
        return Response({'detail': "Utilisateur supprimé avec succès"}, status=status.HTTP_204_NO_CONTENT)




class ProfilUtilisateurView(generics.RetrieveAPIView):
    """GET /utilisateurs/{id} : profil public d'un randonneur."""
    
    serializer_class = ProfilPublicSerializer
    lookup_field = 'pk'

    def get_queryset(self) -> QuerySet[Utilisateur]: #type: ignore[override]
        """
        Depuis la suppression des blocages/comptes privés, 
        tout utilisateur actif est accessible.
        """
        return (
            Utilisateur.objects
            .filter(is_active=True, date_suppression__isnull=True)
            .annotate(
                # Compte le nombre de randonnées PUBLIÉES de cet utilisateur
                nb_randonnees=Count(
                    'randonnees', 
                    filter=Q(randonnees__status_randonnee=StatutRandonnee.PUBLIE),
                    distinct=True
                )
            )
        )





class RechercheUtilisateursView(generics.ListAPIView):
    """GET /recherche/utilisateurs : liste et recherche des randonneurs (?q=texte)."""
    
    filter_backends = []  # Pas de backend DRF, on fait le filtre manuellement

    def get_queryset(self) -> QuerySet[Utilisateur]: #type: ignore[override]
        moi = cast(Utilisateur, self.request.user)
        
        # Base : Tous les utilisateurs actifs, sauf moi-même
        utilisateurs = (
            Utilisateur.objects
            .filter(is_active=True, date_suppression__isnull=True)
            .exclude(pk=moi.pk)
        )

        # Filtre de recherche textuelle
        q = cast(Request, self.request).query_params.get('q', '').strip()[:100]
        if q:
            utilisateurs = utilisateurs.filter(
                Q(nom_complet__icontains=q) | Q(nom_utilisateur__icontains=q)
            )
        
        # Tri stable
        return utilisateurs.order_by('nom_complet', 'id')