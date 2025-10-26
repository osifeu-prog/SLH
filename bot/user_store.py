import json, os, threading

_lock = threading.Lock()

class UserStore:
    def __init__(self, path:str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self):
        with _lock:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _save(self, data):
        with _lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def get_wallet(self, tg_id:str):
        data = self._load()
        u = data.get(str(tg_id), {})
        return u.get("wallet")

    def set_wallet(self, tg_id:str, addr:str):
        data = self._load()
        u = data.get(str(tg_id), {})
        u["wallet"] = addr
        data[str(tg_id)] = u
        self._save(data)

    def get_all(self):
        return self._load()
