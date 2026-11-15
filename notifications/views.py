from typing import cast

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.models import Utilisateur

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """
    GET /notifications : Liste paginée des notifications reçues par l'utilisateur connecté.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self): #type: ignore
        utilisateur = cast(Utilisateur, self.request.user)
        # On ne retourne que les notifications dont l'utilisateur est le destinataire
        return Notification.objects.filter(destinataire=utilisateur).select_related('declencheur', 'randonnee')


class NombreNotificationsNonLuesView(APIView):
    """
    GET /notifications/non-lues/nombre : Renvoie le nombre de notifications non lues.
    Utilisé pour la pastille d'avertissement sur l'icône de cloche.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        utilisateur = cast(Utilisateur, request.user)
        nb_non_lues = Notification.objects.filter(
            destinataire=utilisateur,
            lue=False
        ).count()
        
        return Response({'nombre': nb_non_lues}, status=status.HTTP_200_OK)


class MarquerToutesNotificationsLuesView(APIView):
    """
    POST /notifications/lues : Marquer TOUTES les notifications de l'utilisateur comme lues.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        utilisateur = cast(Utilisateur, request.user)
        nb_modifiees = Notification.objects.filter(
            destinataire=utilisateur,
            lue=False
        ).update(lue=True)

        return Response(
            {'detail': f"{nb_modifiees} notification(s) marquée(s) comme lue(s)."},
            status=status.HTTP_200_OK
        )


class MarquerUneNotificationLueView(APIView):
    """
    POST /notifications/<id>/lue : Marquer UNE notification spécifique comme lue.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        utilisateur = cast(Utilisateur, request.user)
        
        notification = Notification.objects.filter(
            id=pk,
            destinataire=utilisateur
        ).first()

        if notification is None:
            return Response(
                {'detail': "Cette notification n'existe pas ou ne vous est pas destinée."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not notification.lue:
            notification.lue = True
            notification.save(update_fields=['lue'])

        return Response(
            NotificationSerializer(notification, context={'request': request}).data,
            status=status.HTTP_200_OK
        )