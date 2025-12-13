"""
CRUD operations for Provider model.
"""

from fastcrud import FastCRUD

from ..models.provider import Provider
from ..schemas.provider import (
    ProviderCreateInternal,
    ProviderDelete,
    ProviderRead,
    ProviderUpdate,
    ProviderUpdateInternal,
)

CRUDProvider = FastCRUD[
    Provider,
    ProviderCreateInternal,
    ProviderUpdate,
    ProviderUpdateInternal,
    ProviderDelete,
    ProviderRead,
]
crud_provider = CRUDProvider(Provider)

