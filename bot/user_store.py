import os, json, tempfile, asyncio
from typing import Optional

class UserStore:
    def __init__(self, path: str = "data/users.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)
        self._lock = asyncio.Lock()

    async def get_wallet(self, user_id: int) -> Optional[str]:
        async with self._lock:
            data = self._read()
            return data.get(str(user_id), {}).get("wallet")

    async def set_wallet(self, user_id: int, address: str):
        async with self._lock:
            data = self._read()
            u = data.get(str(user_id), {})
            u["wallet"] = address
            data[str(user_id)] = u
            self._write_atomic(data)

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_atomic(self, data: dict):
        d = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(prefix="users.", suffix=".json", dir=d)
        os.close(fd)
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                try: os.remove(tmp)
                except: pass
