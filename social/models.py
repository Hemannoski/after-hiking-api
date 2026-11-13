from django.core.exceptions import ValidationError
from django.db import models


class Commentaire(models.Model):
    """Ce modèle gères tous les commentaires des utilisateurs"""

    randonnee_id: int

    randonnee = models.ForeignKey(
        'randonnees.Randonnee',
        on_delete=models.CASCADE,
        related_name='commentaires',
        help_text="L'identifiant de la randonnée auquel appartient ce commentaire"
    )

    commentateur = models.ForeignKey(
        'comptes.Utilisateur',
        on_delete=models.CASCADE,
        related_name='mes_commentaires',
        help_text="L'identifiant à qui appartient ce commentaire"
    )

    texte = models.TextField(
        help_text="Le contenu du commentaire",
    )

    date_creation_commentaire = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et Heure de création du commentaire"
    )

    class Meta:
        db_table = "commentaires"
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"
        ordering = ['date_creation_commentaire']

    def __str__(self) -> str:
        return f"{self.texte}"


class Like(models.Model):
    """Ce modèle gère les likes des utilisateurs sur une randonnée"""

    auteur = models.ForeignKey(
        'comptes.Utilisateur',
        on_delete=models.CASCADE,
        related_name='mes_likes',
        help_text="L'auteur de ce like"
    )

    randonnee = models.ForeignKey(
        'randonnees.Randonnee',
        on_delete=models.CASCADE,
        related_name='likes',
        help_text="Les randonnées likés"
    )

    date_du_like = models.DateTimeField(
        auto_now_add=True,
        help_text="La date à laquelle la randonnée a été likés"
    )


    class Meta:
        db_table = 'likes'
        verbose_name = 'Like'
        verbose_name_plural = 'Likes'
        ordering = ["-date_du_like"]
        constraints = [
            models.UniqueConstraint(fields=['auteur', 'randonnee'], name='unique_like_par_utilisateur_et_randonnee')
        ]

    def __str__(self) -> str:
        return f"{self.date_du_like} - Date du like"