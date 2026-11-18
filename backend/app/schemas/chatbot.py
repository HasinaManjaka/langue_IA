"""Contrats du relais chatbot entre le backend et le service IA."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ia import MetaExecutionIA

REPONSE_CHATBOT_MAX = 4000
MESSAGE_CHATBOT_MAX = 2000
HISTORIQUE_CHATBOT_MAX = 20


class _ModeleChatbot(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageHistoriqueChatbot(_ModeleChatbot):
    role: Literal["apprenant", "assistant"]
    contenu: str = Field(min_length=1, max_length=REPONSE_CHATBOT_MAX)


class MessageChatbotCreate(_ModeleChatbot):
    message: str = Field(min_length=1, max_length=MESSAGE_CHATBOT_MAX)
    historique: list[MessageHistoriqueChatbot] = Field(default_factory=list, max_length=HISTORIQUE_CHATBOT_MAX)


class ReponseChatbot(_ModeleChatbot):
    reponse: str = Field(min_length=1, max_length=REPONSE_CHATBOT_MAX)


class ContexteChatbotIA(_ModeleChatbot):
    code_langue: Literal["fr", "en", "zh", "it", "de"]
    referentiel: Literal["CECRL", "HSK"]
    niveau_preliminaire: str = Field(min_length=1, max_length=20)


class EntreeChatbotIA(_ModeleChatbot):
    message: str = Field(min_length=1, max_length=MESSAGE_CHATBOT_MAX)
    historique: list[MessageHistoriqueChatbot] = Field(default_factory=list, max_length=HISTORIQUE_CHATBOT_MAX)


class RequeteChatbotIA(_ModeleChatbot):
    request_id: UUID
    contexte: ContexteChatbotIA
    entree: EntreeChatbotIA


class ResultatChatbotIA(_ModeleChatbot):
    reponse: str = Field(min_length=1, max_length=REPONSE_CHATBOT_MAX)


class ReponseChatbotIA(_ModeleChatbot):
    request_id: UUID
    agent: Literal["chatbot"]
    version_agent: str = Field(min_length=1, max_length=32)
    version_prompt: str = Field(min_length=1, max_length=128)
    statut: Literal["succes"] = "succes"
    resultat: ResultatChatbotIA
    meta: MetaExecutionIA
