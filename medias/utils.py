import logging
import time

import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
import cloudinary.utils
from django.conf import settings

logger = logging.getLogger(__name__)

DELAI_CLOUDINARY = 20


def dossier_cloudinary(utilisateur_id: int, randonnee_id: int) -> str:
    return f"after_hiking/utilisateurs/{utilisateur_id}/randonnees/{randonnee_id}"


def generer_signature_upload_cloudinary(utilisateur_id, randonnee_id, resource_type="image"):
    timestamp = int(time.time())
    dossier = dossier_cloudinary(utilisateur_id, randonnee_id)

    signature = cloudinary.utils.api_sign_request(
        {'timestamp': timestamp, 'folder': dossier},
        settings.CLOUDINARY_API_SECRET,
    )

    return {
        'upload_url': f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/{resource_type}/upload",
        'api_key': settings.CLOUDINARY_API_KEY,
        'timestamp': timestamp,
        'signature': signature,
        'folder': dossier,
    }


def _appeler_api_cloudinary(public_id: str, resource_type: str) -> dict | None:
    try:
        return cloudinary.api.resource(
            public_id, resource_type=resource_type, timeout=DELAI_CLOUDINARY,
        )
    except cloudinary.exceptions.NotFound:
        return None
    except cloudinary.exceptions.Error:
        logger.exception("Échec de la vérification Cloudinary (%s)", public_id)
        return None


def verifier_ressource_cloudinary(public_id: str, resource_type: str = "image") -> dict | None:
    """
    Vérifie que le fichier a bien été uploadé et renvoie ses métadonnées réelles.

    Correction #2 : resource_type="auto" n'est pas supporté par api.resource().
    On essaye "image" puis "video" en fallback, et on injecte explicitement
    le type réel dans la réponse (le SDK ne le garantit pas).
    """
    if resource_type == "auto":
        ressource = _appeler_api_cloudinary(public_id, "image")
        if ressource is None:
            ressource = _appeler_api_cloudinary(public_id, "video")
            if ressource is not None:
                ressource["resource_type"] = "video"
        elif ressource is not None:
            ressource["resource_type"] = "image"
        return ressource

    ressource = _appeler_api_cloudinary(public_id, resource_type)
    if ressource is not None:
        ressource["resource_type"] = resource_type
    return ressource


def supprimer_fichier_cloudinary(public_id: str, resource_type: str = "image") -> None:
    """Supprime le fichier distant. Un échec est journalisé, jamais propagé."""
    if not public_id:
        return
    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type,
            invalidate=True,
            timeout=DELAI_CLOUDINARY,
        )
    except cloudinary.exceptions.Error:
        logger.exception("Échec de la suppression Cloudinary (%s)", public_id)