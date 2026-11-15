from rest_framework import serializers

from .models import Commentaire


class CommentaireSerializer(serializers.ModelSerializer):
    """
    Serializer pour l'affichage d'un commentaire.
    Inclut les infos de l'auteur pour éviter un appel supplémentaire.
    """

    auteur_nom = serializers.CharField(source='commentateur.nom_complet', read_only=True)
    auteur_nom_utilisateur = serializers.CharField(source='commentateur.nom_utilisateur', read_only=True)
    auteur_photo = serializers.CharField(source='commentateur.photo_profil', read_only=True)

    class Meta:
        model = Commentaire
        fields = [
            'id',
            'randonnee',
            'commentateur',
            'auteur_nom',
            'auteur_nom_utilisateur',
            'auteur_photo',
            'texte',
            'date_creation_commentaire',
        ]
        read_only_fields = [
            'id', 'randonnee', 'commentateur',
            'auteur_nom', 'auteur_nom_utilisateur', 'auteur_photo',
            'date_creation_commentaire',
        ]


class CreerCommentaireSerializer(serializers.ModelSerializer):
    """
    Valide le corps de POST /randonnees/{id}/commentaires.
    Seul le texte est requis (l'auteur et la randonnée sont injectés par la vue).
    """

    texte = serializers.CharField(
        required=True,
        allow_blank=False,
        min_length=1,
        max_length=1000,
        error_messages={
            'blank': "Le texte du commentaire ne peut pas être vide.",
            'required': "Le texte du commentaire est obligatoire.",
        }
    )

    class Meta:
      model = Commentaire
      fields = ['texte']