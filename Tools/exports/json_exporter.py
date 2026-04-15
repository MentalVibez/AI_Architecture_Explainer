from ..backend_bridge import load_backend_module

export = load_backend_module("app.services.reviewer.exports.json_exporter").export

__all__ = ["export"]
