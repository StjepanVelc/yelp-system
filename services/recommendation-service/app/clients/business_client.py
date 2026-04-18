import grpc
from app.grpc import business_pb2, business_pb2_grpc
from app.core.config import settings


def _get_stub():
    channel = grpc.insecure_channel(settings.business_service_grpc)
    return business_pb2_grpc.BusinessServiceStub(channel)


def get_business(business_id: str) -> dict | None:
    stub = _get_stub()
    try:
        response = stub.GetBusiness(
            business_pb2.GetBusinessRequest(business_id=business_id)
        )
        return _proto_to_dict(response)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return None
        raise


def list_businesses_in_area(city: str, state: str, limit: int = 1000) -> list[dict]:
    stub = _get_stub()
    response = stub.ListBusinesses(
        business_pb2.ListBusinessesRequest(city=city, state=state, limit=limit, page=1)
    )
    return [_proto_to_dict(b) for b in response.businesses]


def _proto_to_dict(b) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "city": b.city,
        "state": b.state,
        "stars": b.stars,
        "review_count": b.review_count,
        "is_open": b.is_open,
        "categories": b.categories,
        "latitude": b.latitude,
        "longitude": b.longitude,
        "address": b.address,
        "postal_code": b.postal_code,
    }
