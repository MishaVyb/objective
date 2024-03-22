import schemathesis
from schemathesis.models import Case

from objective.settings import settings
from objective.web.application import get_app

app = get_app()
schema = schemathesis.from_asgi(settings.openapi_url, app, force_schema_version="30")


@schema.parametrize(endpoint="/api/users/me")
def test_api(case: Case):
    response = case.call_asgi()
    case.validate_response(response)
