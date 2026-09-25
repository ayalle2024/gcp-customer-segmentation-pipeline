"""Cliente para la API pública de RandomUser.me (https://randomuser.me)."""

from typing import Any, Dict, List

import requests

from src.app.core.config import RANDOM_USER_URL, SERVICE_NAME
from src.app.utils.logging import get_logger

logger = get_logger(SERVICE_NAME)


class RandomUserError(RuntimeError):
    """Error consultando la API de RandomUser.me (red, timeout o respuesta inválida)."""


def fetch_random_users(count: int, timeout: int = 15) -> List[Dict[str, Any]]:
    logger.info("Consultando RandomUser.me (results=%s)", count)

    try:
        response = requests.get(RANDOM_USER_URL, params={"results": count}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RandomUserError(f"Fallo de red consultando RandomUser.me: {e}") from e

    try:
        return response.json().get("results", [])
    except ValueError as e:
        raise RandomUserError(f"Respuesta inesperada de RandomUser.me (no es JSON válido): {e}") from e
