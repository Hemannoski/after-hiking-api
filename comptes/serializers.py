from rest_framework import serializers
from .validators import valider_photo_profil

from .models import Utilisateur


class InscriptionSerializer(serializers.ModelSerializer):
    """Valide le corps de POST /auth/firebase à la création du compte."""

    # Nom d'utilisateur proposé par l'application (généré et affiché dans le formulaire)
    nom_utilisateur = serializers.RegexField(
        regex=r'^@[a-z0-9_]{1,44}[0-9]{5}$',
        max_length=50,
        required=False,
    )

    class Meta:
        model = Utilisateur
        fields = ['nom_complet', 'nom_utilisateur', 'ville', 'bio']
        extra_kwargs = {
            'nom_complet': {'required': True, 'allow_blank': False, 'allow_null': False},
        }


class UtilisateurSerializer(serializers.ModelSerializer):
    """Profil renvoyé par l'API (lecture seule)."""

    class Meta:
        model = Utilisateur
        fields = ['id', 'firebase_uid', 'photo_profil', 'date_creation', 'is_active', 'is_staff', 
                  'is_superuser', 'nom_complet', 'nom_utilisateur', 'ville', 'bio']
        read_only_fields = fields

class PhotoProfilSerializer(serializers.Serializer):
    """Valide le corps de POST /moi/photo : un seul champ, le fichier 'photo'."""

    photo = serializers.FileField(
        allow_empty_file=False,
        validators=[valider_photo_profil],
    )

class ModifierProfilSerializer(serializers.ModelSerializer):
    """Valide le corps de PATCH /moi : liste blanche des champs modifiables."""

    class Meta:
        model = Utilisateur
        fields = ['nom_complet', 'ville', 'bio']
        extra_kwargs = {
            'nom_complet': {'allow_blank': False, 'allow_null': False},
        }

class ProfilPublicSerializer(serializers.ModelSerializer):
    """Profil d'un autre randonneur (lecture seule). Les totaux viennent de la vue."""

    nb_randonnees = serializers.IntegerField(read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'nom_utilisateur', 'nom_complet', 'bio', 'ville', 'photo_profil', 'nb_randonnees']
        read_only_fields = fields
