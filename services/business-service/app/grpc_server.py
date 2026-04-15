import grpc
from concurrent import futures
from app.grpc import business_pb2, business_pb2_grpc
from app.db.session import SessionLocal
from app.repository.business_repository import get_businesses, get_business_by_id


class BusinessServicer(business_pb2_grpc.BusinessServiceServicer):

    def GetBusiness(self, request, context):
        db = SessionLocal()
        try:
            row = get_business_by_id(db, request.business_id)
            if not row:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Business not found")
                return business_pb2.BusinessResponse()
            return _to_proto(row)
        finally:
            db.close()

    def ListBusinesses(self, request, context):
        db = SessionLocal()
        try:
            rows = get_businesses(
                db,
                city=request.city or None,
                min_stars=request.min_stars or None,
                limit=request.limit or 20,
                offset=(max(request.page, 1) - 1) * (request.limit or 20),
            )
            businesses = [_to_proto(r) for r in rows]
            return business_pb2.ListBusinessesResponse(businesses=businesses)
        finally:
            db.close()


def _to_proto(row: dict) -> business_pb2.BusinessResponse:
    return business_pb2.BusinessResponse(
        id=row.get("id", ""),
        name=row.get("name", "") or "",
        city=row.get("city", "") or "",
        state=row.get("state", "") or "",
        stars=float(row.get("stars") or 0),
        review_count=int(row.get("review_count") or 0),
        is_open=bool(row.get("is_open")),
        categories=row.get("categories", "") or "",
        latitude=float(row.get("latitude") or 0),
        longitude=float(row.get("longitude") or 0),
        address=row.get("address", "") or "",
        postal_code=row.get("postal_code", "") or "",
    )


def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    business_pb2_grpc.add_BusinessServiceServicer_to_server(BusinessServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    return server
