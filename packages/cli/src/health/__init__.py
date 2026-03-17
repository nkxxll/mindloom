import httpx


class Health:
    def __init__(self, config):
        self.config = config

    def get_health(self) -> bool:
        res = httpx.get(f"{self.config.host}/health")
        if res.status_code == 200:
            return True
        return False
