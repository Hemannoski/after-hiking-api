from rest_framework import serializers

from social.models import Like

from .models import Randonnee


class RandonneeCreateSerializer(serializers.ModelSerializer):
    """POST /randonnees : création d'une randonnée en brouillon."""

    class Meta:
        model = Randonnee
        fields = [
            'id',
            'titre_randonnee',
            'lieu_randonnee',
            'date_randonnee',
            'distance_randonnee_km',
            'duree_randonnee_minutes',
            'description_randonnee',
            'niveau_difficulte_randonnee',
        ]
        read_only_fields = ['id']


class RandonneeUpdateSerializer(serializers.ModelSerializer):
    """PATCH /randonnees/{id} : modification de sa randonnée (brouillon uniquement)."""

    class Meta:
        model = Randonnee
        fields = [
            'titre_randonnee',
            'lieu_randonnee',
            'date_randonnee',
            'distance_randonnee_km',
            'duree_randonnee_minutes',
            'description_randonnee',
            'niveau_difficulte_randonnee',
        ]
        extra_kwargs = {
            'titre_randonnee': {'allow_blank': False},
            'lieu_randonnee': {'allow_blank': False},
            'description_randonnee': {'allow_blank': False},
        }


class RandonneeListeSerializer(serializers.ModelSerializer):
    """GET /moi/brouillons : liste des brouillons de l'utilisateur connecté."""

    class Meta:
        model = Randonnee
        fields = [
            'id',
            'titre_randonnee',
            'lieu_randonnee',
            'date_randonnee',
            'status_randonnee',
            'date_publication_randonnee',
        ]
        read_only_fields = fields


class RandonneeDetailSerializer(serializers.ModelSerializer):
    """
    Détail complet d'une randonnée (GET /randonnees/{id}).
    
    Tous les compteurs proviennent directement de StatistiqueRandonnee (0 requête supplémentaire).
    Seul 'a_jaime' exécute 1 requête ciblée (EXISTS) pour l'utilisateur connecté.
    """

    media_couverture_url = serializers.CharField(
        source='media_couverture.url_media', 
        read_only=True, 
        default=None
    )
    
    # Compteurs centralisés dans StatistiqueRandonnee
    nombre_likes = serializers.IntegerField(source='statistiques.nombre_likes', read_only=True, default=0)
    nombre_commentaires = serializers.IntegerField(source='statistiques.nombre_commentaires', read_only=True, default=0)
    nombre_medias = serializers.IntegerField(source='statistiques.nombre_medias', read_only=True, default=0)
    nombre_vues = serializers.IntegerField(source='statistiques.nombre_vues', read_only=True, default=0)
    
    # État du like pour l'utilisateur connecté
    a_jaime = serializers.SerializerMethodField()

    class Meta:
        model = Randonnee
        fields = [
            'id',
            'auteur',
            'media_couverture',
            'media_couverture_url',
            'titre_randonnee',
            'lieu_randonnee',
            'date_randonnee',
            'date_publication_randonnee',
            'status_randonnee',
            'distance_randonnee_km',
            'duree_randonnee_minutes',
            'description_randonnee',
            'niveau_difficulte_randonnee',
            'nombre_likes',
            'nombre_commentaires',
            'nombre_medias',
            'nombre_vues',
            'a_jaime',
        ]
        read_only_fields = fields

    def get_a_jaime(self, obj: Randonnee) -> bool:
        """Exécute 1 requête ciblée (EXISTS) pour vérifier le like de l'utilisateur actuel."""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            return Like.objects.filter(randonnee=obj, auteur=request.user).exists()
        return False


class RandonneeFilSerializer(serializers.ModelSerializer):
    """
    Serializer pour le fil d'actualités (GET /fil).
    Affiche les cartes du fil d'actualité.
    """

    auteur_nom_utilisateur = serializers.CharField(source='auteur.nom_utilisateur', read_only=True)
    auteur_nom_complet = serializers.CharField(source='auteur.nom_complet', read_only=True)
    auteur_photo = serializers.CharField(source='auteur.photo_profil', read_only=True)
    media_couverture_url = serializers.SerializerMethodField()

    # Compteurs depuis StatistiqueRandonnee (syntaxe corrigée avec le point)
    nombre_likes = serializers.IntegerField(source='statistiques.nombre_likes', read_only=True, default=0)
    nombre_commentaires = serializers.IntegerField(source='statistiques.nombre_commentaires', read_only=True, default=0)

    class Meta:
        model = Randonnee
        fields = [
            'id',
            'auteur_nom_utilisateur',
            'auteur_nom_complet',
            'auteur_photo',
            'media_couverture_url',
            'titre_randonnee',
            'lieu_randonnee',
            'date_randonnee',
            'date_publication_randonnee',
            'distance_randonnee_km',
            'duree_randonnee_minutes',
            'niveau_difficulte_randonnee',
            'nombre_likes',
            'nombre_commentaires',
        ]
        read_only_fields = fields

    def get_media_couverture_url(self, obj: Randonnee):
        if obj.media_couverture is not None:
            return obj.media_couverture.url_media
        return None


class RandonneeRechercheSerializer(serializers.ModelSerializer):
    """
    Serializer pour les résultats de recherche de randonnées (GET /recherche/randonnees).
    """

    auteur_nom_utilisateur = serializers.CharField(source='auteur.nom_utilisateur', read_only=True)
    media_couverture_url = serializers.SerializerMethodField()

    class Meta:
        model = Randonnee
        fields = [
            'id',
            'auteur_nom_utilisateur',
            'media_couverture_url',
            'titre_randonnee',
            'lieu_randonnee',
            'date_randonnee',
            'distance_randonnee_km',
            'duree_randonnee_minutes',
            'niveau_difficulte_randonnee',
        ]
        read_only_fields = fields

    def get_media_couverture_url(self, obj: Randonnee):
        if obj.media_couverture is not None:
            return obj.media_couverture.url_media
        return None