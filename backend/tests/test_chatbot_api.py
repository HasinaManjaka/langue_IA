"""Tests de la route authentifiée du relais chatbot."""

from uuid import UUID

import pytest

from app.models import Role
from app.schemas.chatbot import ReponseChatbotIA, RequeteChatbotIA, ResultatChatbotIA
from app.schemas.ia import MetaExecutionIA
from app.seed_us156 import charger_contenu_demo_us156
from app.services.ia import ErreurServiceIA
from tests.conftest import creer_utilisateur, entete

BASE = "/api/v1/chatbot/message"
REQUEST_ID = UUID("6d0e9f6a-2d7b-4c31-9f9b-8a0f1f2c3d4e")


def _enveloppe(reponse: str = "Bonjour !") -> ReponseChatbotIA:
    return ReponseChatbotIA(
        request_id=REQUEST_ID,
        agent="chatbot",
        version_agent="1.0.0",
        version_prompt="chatbot/conversation@1.0.0",
        resultat=ResultatChatbotIA(reponse=reponse),
        meta=MetaExecutionIA(
            duree_ms=120,
            fournisseur="factice",
            modele="modele-test",
            empreinte_prompt="sha256:" + "a" * 64,
        ),
    )


def _relais(monkeypatch: pytest.MonkeyPatch, appels: list[RequeteChatbotIA], erreur: str | None = None) -> None:
    def faux_appel(requete: RequeteChatbotIA) -> ReponseChatbotIA:
        appels.append(requete)
        if erreur is not None:
            raise ErreurServiceIA(erreur)
        return _enveloppe()

    monkeypatch.setattr("app.api.routes.chatbot.envoyer_message_chatbot", faux_appel)


def test_chatbot_refuse_une_session_absente(client) -> None:
    reponse = client.post(BASE, json={"message": "Bonjour", "historique": []})

    assert reponse.status_code == 401


def test_chatbot_refuse_un_non_apprenant(db, client) -> None:
    formateur = creer_utilisateur(db, role=Role.FORMATEUR, email="formateur@exemple.com")

    reponse = client.post(
        BASE,
        json={"message": "Bonjour", "historique": []},
        headers=entete(formateur),
    )

    assert reponse.status_code == 403


def test_chatbot_relais_authentifie(db, client, monkeypatch: pytest.MonkeyPatch) -> None:
    apprenant = creer_utilisateur(db, email="apprenant@digitheque.mg", prenom="Rova", nom="RAKOTO")
    charger_contenu_demo_us156(db)
    appels: list[RequeteChatbotIA] = []
    _relais(monkeypatch, appels)

    reponse = client.post(
        BASE,
        json={
            "message": "Comment vas-tu ?",
            "historique": [{"role": "assistant", "contenu": "Bonjour !"}],
        },
        headers=entete(apprenant),
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"reponse": "Bonjour !"}
    assert len(appels) == 1
    requete = appels[0]
    assert requete.contexte.code_langue == "en"
    assert requete.contexte.referentiel == "CECRL"
    assert requete.contexte.niveau_preliminaire == "A2"
    assert requete.entree.message == "Comment vas-tu ?"
    assert [tour.role for tour in requete.entree.historique] == ["assistant"]


def test_chatbot_sans_parcours_utilise_un_contexte_minimal(db, client, monkeypatch: pytest.MonkeyPatch) -> None:
    apprenant = creer_utilisateur(db)
    appels: list[RequeteChatbotIA] = []
    _relais(monkeypatch, appels)

    reponse = client.post(BASE, json={"message": "Salut"}, headers=entete(apprenant))

    assert reponse.status_code == 200
    assert appels[0].contexte.code_langue == "en"
    assert appels[0].contexte.niveau_preliminaire == "A1"
    assert appels[0].entree.historique == []


@pytest.mark.parametrize(
    ("code", "statut"),
    [
        ("non_configure", 503),
        ("timeout", 504),
        ("indisponible", 502),
        ("reponse_invalide", 502),
        ("http_422", 422),
        ("http_429", 429),
        ("http_500", 502),
    ],
)
def test_erreur_du_service_ia_est_traduite(db, client, monkeypatch: pytest.MonkeyPatch, code: str, statut: int) -> None:
    apprenant = creer_utilisateur(db)
    appels: list[RequeteChatbotIA] = []
    _relais(monkeypatch, appels, erreur=code)

    reponse = client.post(BASE, json={"message": "Salut"}, headers=entete(apprenant))

    assert reponse.status_code == statut
    assert len(appels) == 1
    assert "detail" in reponse.json()


@pytest.mark.parametrize(
    "corps",
    [
        {"message": "", "historique": []},
        {"message": "Salut", "historique": [{"role": "inconnu", "contenu": "Bonjour"}]},
        {"message": "Salut", "historique": [{"role": "assistant", "contenu": "x"}] * 21},
        {"message": "Salut", "historique": [], "champ_inconnu": True},
        {"message": "Salut", "historique": [{"role": "assistant", "contenu": ""}]},
    ],
    ids=["message-vide", "role-inconnu", "historique-trop-long", "champ-en-trop", "tour-vide"],
)
def test_corps_hors_contrat_refuse(db, client, corps: dict) -> None:
    apprenant = creer_utilisateur(db)

    reponse = client.post(BASE, json=corps, headers=entete(apprenant))

    assert reponse.status_code == 422
