from django.contrib import admin

from .models import Commentaire, Like


@admin.register(Commentaire)
class CommentaireAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour le modèle Commentaire."""


    @admin.display(description="Aperçu du commentaire")
    def texte_court(self, obj):
        return obj.texte[: 50] + "..." if len(obj.texte) > 50 else obj.texte



    # --- 1. AFFICHAGE DE LA LISTE DES COMMENTAIRES ---

    list_display = [
        "texte_court",
        "randonnee",
        "commentateur",
        "date_creation_commentaire",
    ]


    # Filtres latéraux (à droite de la liste)
    list_filter = [
        "date_creation_commentaire",
        "randonnee",
    ]

    # Barre de recherche en haut
    search_fields = [
        "texte",
        "commentateur__nom_utilisateur",
    ]

    # Tri par défaut (du plus récent au plus ancien)
    ordering = ["-date_creation_commentaire"]


    # Pagination (nombre de randonnee par page)
    list_per_page = 25
        




@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour le modèle Like."""


    # --- 1. AFFICHAGE DE LA LISTE DES LIKE ---

    list_display = [
        "auteur",
        "randonnee",
        "date_du_like",
    ]


    # Filtres latéraux (à droite de la liste)
    list_filter = [
        "randonnee",
        "date_du_like"
    ]

    # Barre de recherche en haut
    search_fields = [
        "randonnee__titre_randonnee",
    ]

    # Tri par défaut (du plus récent au plus ancien)
    ordering = ["-date_du_like"]


    # Pagination (nombre de Like par page)
    list_per_page = 25