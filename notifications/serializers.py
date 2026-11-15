from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer pour le modèle Notification (Lecture seule).
    Enrichit l'objet retourné avec les informations du déclencheur et de la randonnée.
    """

    # Champs calculés pour simplifier l'affichage côté React Native
    declencheur_nom_utilisateur = serializers.CharField(source='declencheur.nom_utilisateur', read_only=True, default=None)
    declencheur_photo_profil = serializers.CharField(source='declencheur.photo_profil', read_only=True, default=None)
    randonnee_titre = serializers.CharField(source='randonnee.titre_randonnee', read_only=True, default=None)

    class Meta:
        model = Notification
        fields = [
            'id',
            'type_notification',
            'lue',
            'date_notification',
            'declencheur',
            'declencheur_nom_utilisateur',
            'declencheur_photo_profil',
            'randonnee',
            'randonnee_titre',
        ]
        read_only_fields = fields