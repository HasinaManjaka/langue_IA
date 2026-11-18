"""Fixtures partagées des tests du service IA."""

import pytest

VARIABLES_LLM = (
    "ENVIRONNEMENT",
    "LLM_FOURNISSEUR",
    "LLM_FACTICE_SCENARIO",
    "LLM_MODELE",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_TIMEOUT",
    "LLM_TIMEOUT_S",
    "LLM_MAX_RETRIES",
    "LLM_REPRISE_DELAI_S",
    "LLM_REPRISE_DELAI_MAX_S",
    "LLM_BUDGET_TOTAL_S",
    "RAG_CORPUS_ACTIF",
    "RAG_CORPUS_CHEMIN",
    "RAG_CORPUS_VERIFIER_EMPREINTE",
)


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supprime les variables injectées par Compose pour rendre les tests déterministes."""
    for nom in VARIABLES_LLM:
        monkeypatch.delenv(nom, raising=False)


@pytest.fixture
def env_propre(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Conserve l'ancien nom de fixture pour les tests qui la demandent explicitement."""
    return monkeypatch
