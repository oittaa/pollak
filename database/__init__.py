from logging import getLogger
from time import time

log = getLogger(__name__)

class Cache():
    def __init__(self, threshold=1000, default_timeout=300):
        self._cache = {}
        self._threshold = threshold
        self.default_timeout = default_timeout

    def _prune(self):
        if len(self._cache) > self._threshold:
            now = time()
            toremove = []
            for idx, (key, (expires, _)) in enumerate(self._cache.items()):
                if (expires != 0 and expires <= now) or idx % 3 == 0:
                    toremove.append(key)
            for key in toremove:
                self._cache.pop(key, None)

    def _normalize_timeout(self, timeout):
        if timeout is None:
            timeout = self.default_timeout
        if timeout > 0:
            timeout = time() + timeout
        return timeout

    def get(self, key):
        try:
            expires, value = self._cache[key]
            if expires == 0 or expires > time():
                return value
        except (KeyError):
            return None

    def set(self, key, value, timeout=None):
        expires = self._normalize_timeout(timeout)
        self._prune()
        self._cache[key] = (
            expires,
            value
        )
        return True

    def add(self, key, value, timeout=None):
        expires = self._normalize_timeout(timeout)
        self._prune()
        item = (expires, value)
        if key in self._cache:
            return False
        self._cache.setdefault(key, item)
        return True

    def delete(self, key):
        return self._cache.pop(key, None) is not None

    def has(self, key):
        try:
            expires, value = self._cache[key]
            return expires == 0 or expires > time()
        except KeyError:
            return False

# Memory database for local testing
class MemoryDatabase:
    def __init__(self, threshold=10000, default_timeout=0):        
        log.warning('Using: MemoryDatabase - All data will be lost on restart!')

        self.cache = Cache(threshold=threshold, default_timeout=default_timeout)

    def add_user(self, user_id, token, vehicle_id, begins_at, expires_at):
        data = {
            "token": token,
            "vehicle_id": vehicle_id,
            "begins_at": begins_at,
            "expires_at": expires_at
        }
        self.cache.add(user_id, data)
        return True

    def get_user(self, user_id):
        return self.cache.get(user_id)

    def delete_user(self, user_id):
        self.cache.delete(user_id)
        return True

    def cleanup(self):
        return True

# Cloud Firestore https://cloud.google.com/firestore/docs/quickstart-servers
class Firestore:
    def __init__(self, cache_threshold=1000, cache_timeout=300, cache_miss=True):
        from google.cloud import firestore
        import google.cloud.exceptions

        log.info('Using: Cloud Firestore')

        self.cache = Cache(threshold=cache_threshold, default_timeout=cache_timeout)
        self.cache_miss = cache_miss
        self.db = firestore.Client()

    def add_user(self, user_id, token, vehicle_id, begins_at, expires_at):
        data = {
            "token": token,
            "vehicle_id": vehicle_id,
            "begins_at": begins_at,
            "expires_at": expires_at
        }
        self.db.collection(u'users').document(user_id).set(data)
        self.cache.add(user_id, data)
        return True

    def get_user(self, user_id):
        data = self.cache.get(user_id)
        if data is not None:
            return data

        doc_ref = self.db.collection(u'users').document(user_id)
        try:
            doc = doc_ref.get()
            data = doc.to_dict()
            if self.cache_miss and data is None:
                self.cache.add(user_id, False)
            else:
                self.cache.add(user_id, data)
            return data
        except google.cloud.exceptions.NotFound:
            return False

    def delete_user(self, user_id):
        self.db.collection(u'users').document(user_id).delete()
        self.cache.delete(user_id)
        return True

    def cleanup(self):
        now = int(time())
        docs = self.db.collection(u'users').where(u'expires_at', u'<=', now).stream()
        counter = 0
        for doc in docs:
            doc.reference.delete()
            counter = counter + 1
        log.info('Deleted %d documents.', counter)
        return True
