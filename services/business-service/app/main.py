import threading
from fastapi import FastAPI
from app.api.routes import router
from app.db.session import engine
from app.models.business import Base
from app.core.logger import get_logger

log = get_logger("business-service")
app = FastAPI(title="Business Service", version="1.0.0")


@app.on_event("startup")
def startup():
    log.info("Business service starting up")
    Base.metadata.create_all(bind=engine)
    log.info("Database tables verified/created")
    from app.grpc_server import serve
    grpc_server = serve(port=50051)
    t = threading.Thread(target=grpc_server.wait_for_termination, daemon=True)
    t.start()
    log.info("gRPC server started on port 50051")


app.include_router(router, prefix="/businesses")

