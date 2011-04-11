from django.http import HttpResponse
from api.models import APIUser
from piston.decorator import decorator
from piston.utils import rc, HttpStatusCode


def require_api_user(*ff):
    @decorator 
    def wrap(f, self, request, *args, **kwargs):
        try:
            api_user_key = request.data.get("request").get("api_user_key")
            api_user = APIUser.objects.get(key=api_user_key, active=True)
            kwargs["api_user"] = api_user
        except (AttributeError, APIUser.DoesNotExist):
            return rc.FORBIDDEN

        return f(self, request, *args, **kwargs)
    return wrap


def handle_request_payload():
    @decorator
    def wrap(f, self, request, *args, **kwargs):
        payload = self.data
        if isinstance(payload, HttpResponse) and hasattr(payload, "data"):
            self.payload_request = payload
            self.data = payload.data

        stream = f(self, request, *args, **kwargs)

        if hasattr(self, "payload_request"):
            self.payload_request.content = stream
            raise HttpStatusCode(self.payload_request)

        return stream

    return wrap

