import argparse
import logging
import threading

from . import analysis, config, db, seed
from .server import make_server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="soil_service", description="Nutrient & Soil microservice")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "worker"],
                        help="serve: web API and web app (default); worker: background analysis only")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_schema()
    seed.run()

    if args.command == "worker":
        analysis.run_worker()
        return 0

    if config.RUN_WORKER_IN_API:
        threading.Thread(target=analysis.run_worker, name="soil-worker", daemon=True).start()
    server = make_server()
    print(f"Nutrient & Soil service running: http://localhost:{config.PORT}/  "
          f"(API: /api/v1/soil, description: /api/v1/soil/openapi.json)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
