# Register all mapped models for Alembic / test schema creation.
from app.modules.audit.models import AuditEvent  # noqa: F401
from app.modules.customers.models import Customer  # noqa: F401
from app.modules.organizations.models import Organization  # noqa: F401
from app.modules.users.models import User  # noqa: F401
