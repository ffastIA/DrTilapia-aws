# CAMINHO: backend/app/services/user_profile_service.py

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from postgrest.exceptions import APIError

from app.database import get_user_scoped_client
from app.profile_schemas import ProfileUpsertRequest

logger = logging.getLogger(__name__)

_PROFILE_COLUMNS = (
    "user_id, sequential_id, full_name, phone, instagram, linkedin, "
    "company_name, cnpj, farming_type, annual_production_tons, contact_role, "
    "water_surface_area_ha, tank_count, predominant_species, company_website, "
    "address_street, address_number, address_complement, address_zip_code, "
    "address_city, address_state, created_at, updated_at"
)


class UserProfileService:
    def _get_email(self, user_id: str, access_token: str) -> str:
        client = get_user_scoped_client(access_token)
        result = client.table("users").select("email").eq("id", user_id).execute()
        if not result.data:
            raise ValueError("Usuário não encontrado")
        return result.data[0]["email"]

    def _row_to_dict(self, row: Optional[dict], email: str) -> Dict[str, Any]:
        if row is None:
            return {"has_profile": False, "email": email}
        data = dict(row)
        data["has_profile"] = True
        data["email"] = email
        data["created_at"] = str(data["created_at"]) if data.get("created_at") else None
        data["updated_at"] = str(data["updated_at"]) if data.get("updated_at") else None
        data.pop("user_id", None)
        return data

    def get_profile(self, user_id: str, access_token: str) -> Dict[str, Any]:
        email = self._get_email(user_id, access_token)
        client = get_user_scoped_client(access_token)
        result = (
            client.table("user_profiles")
            .select(_PROFILE_COLUMNS)
            .eq("user_id", user_id)
            .execute()
        )
        row = result.data[0] if result.data else None
        return self._row_to_dict(row, email)

    def upsert_profile(
        self, user_id: str, access_token: str, data: ProfileUpsertRequest
    ) -> Dict[str, Any]:
        email = self._get_email(user_id, access_token)
        client = get_user_scoped_client(access_token)

        payload = data.model_dump(exclude_none=True)
        for key in ("annual_production_tons", "water_surface_area_ha"):
            if key in payload and isinstance(payload[key], Decimal):
                payload[key] = float(payload[key])
        payload["user_id"] = user_id

        try:
            result = (
                client.table("user_profiles")
                .upsert(payload, on_conflict="user_id")
                .execute()
            )
        except APIError as exc:
            logger.warning("[user_profile_service] upsert rejeitado: %s", exc)
            raise ValueError(f"Não foi possível salvar o perfil: {exc.message}") from exc

        if not result.data:
            raise ValueError("Não foi possível salvar o perfil")

        logger.info("[user_profile_service] perfil salvo user_id=%s", user_id)
        return self._row_to_dict(result.data[0], email)


user_profile_service = UserProfileService()
