from rest_framework import serializers

from .models import Media, TypeMedias


class AutorisationMediaSerializer(serializers.Serializer):
    type_media = serializers.ChoiceField(choices=TypeMedias.choices)
    taille_en_octet = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        limite = 10 * 1024 * 1024 if attrs['type_media'] == TypeMedias.PHOTO else 100 * 1024 * 1024
        if attrs['taille_en_octet'] > limite:
            raise serializers.ValidationError(
                {'taille_en_octet': "Ce fichier dépasse la taille maximale autorisée."}
            )
        return attrs


class EnregistrerMediaSerializer(serializers.ModelSerializer):
    """Corps de POST /randonnees/{id}/medias. Aucun statut : c'est le serveur qui décide."""

    class Meta:
        model = Media
        fields = [
            'url_media', 'public_id', 'type_media',
            'taille_en_octet', 'duree_video_en_seconde',
        ]
        extra_kwargs = {
            'url_media': {'required': True},
            'public_id': {'required': True, 'allow_blank': False},
            'taille_en_octet': {'required': True},
        }


class MediaSerializer(serializers.ModelSerializer):
    est_couverture = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = [
            'id', 'type_media', 'url_media', 'duree_video_en_seconde',
            'ordre', 'status_traitement', 'est_couverture',
        ]

    def get_est_couverture(self, obj):
        return obj.randonnee.media_couverture_id == obj.id


class ChoisirCouvertureSerializer(serializers.Serializer):
    media_id = serializers.IntegerField(required=True)


class ItemOrdreSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    ordre = serializers.IntegerField(min_value=0, required=True)


class ReordonnerMediasSerializer(serializers.Serializer):
    ordres = ItemOrdreSerializer(many=True, required=True)

    def validate_ordres(self, valeur):
        positions = [item['ordre'] for item in valeur]
        if len(positions) != len(set(positions)):
            raise serializers.ValidationError("Deux médias ne peuvent pas occuper la même position.")

        identifiants = [item['id'] for item in valeur]
        if len(identifiants) != len(set(identifiants)):
            raise serializers.ValidationError("Un même média apparaît plusieurs fois.")
        return valeur