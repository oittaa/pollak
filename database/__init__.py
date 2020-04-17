"""Database backends."""
from logging import getLogger
from time import time
from google.cloud import firestore
import google.cloud.exceptions

LOG = getLogger(__name__)

class Cache():
    """Local memory cache class for databases."""
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
        """Return item from cache, if it has not expired."""
        try:
            expires, value = self._cache[key]
            if expires == 0 or expires > time():
                return value
        except KeyError:
            pass
        return None

    def set(self, key, value, timeout=None):
        """Set key with value."""
        expires = self._normalize_timeout(timeout)
        self._prune()
        self._cache[key] = (
            expires,
            value
        )
        return True

    def add(self, key, value, timeout=None):
        """Add new key with value if it does not exist."""
        expires = self._normalize_timeout(timeout)
        self._prune()
        item = (expires, value)
        if key in self._cache:
            return False
        self._cache.setdefault(key, item)
        return True

    def delete(self, key):
        """Delete a key from the cache."""
        return self._cache.pop(key, None) is not None

    def has(self, key):
        """Check if a key exists in the cache."""
        try:
            expires, _value = self._cache[key]
            return expires == 0 or expires > time()
        except KeyError:
            return False

    def cleanup(self):
        """Delete expired items from the cache."""
        now = time()
        toremove = []
        for _idx, (key, (expires, _)) in enumerate(self._cache.items()):
            if expires != 0 and expires <= now:
                toremove.append(key)
        for key in toremove:
            self._cache.pop(key, None)

# Memory database for local testing
class MemoryDatabase:
    """Temporary in-memory database backend for testing."""
    def __init__(self, threshold=10000, default_timeout=0):
        LOG.warning('Using: MemoryDatabase - All data will be lost on restart!')

        self.cache = Cache(threshold=threshold, default_timeout=default_timeout)

    def add_user(self, user_id, data):
        """Add user with submitted data to database."""
        self.cache.add(user_id, data)
        return True

    def get_user(self, user_id):
        """Return user data from database."""
        return self.cache.get(user_id)

    def delete_user(self, user_id):
        """Delete user data from database."""
        self.cache.delete(user_id)
        return True

    def cleanup(self):
        """Delete expired users from database."""
        self.cache.cleanup()
        return True

# Cloud Firestore https://cloud.google.com/firestore/docs/quickstart-servers
class Firestore:
    """Cloud Firestore database backend."""
    def __init__(self, cache_threshold=1000, cache_timeout=300, cache_miss=True):
        LOG.info('Using: Cloud Firestore')

        self.cache = Cache(threshold=cache_threshold, default_timeout=cache_timeout)
        self.cache_miss = cache_miss
        self.db_client = firestore.Client()

    def add_user(self, user_id, data):
        """Add user with submitted data to database."""
        self.db_client.collection(u'users').document(user_id).set(data)
        self.cache.add(user_id, data)
        return True

    def get_user(self, user_id):
        """Return user data from database."""
        data = self.cache.get(user_id)
        if data is not None:
            return data

        doc_ref = self.db_client.collection(u'users').document(user_id)
        doc = doc_ref.get()
        data = doc.to_dict()
        if data:
            self.cache.add(user_id, data)
        elif self.cache_miss:
            self.cache.add(user_id, False)
        return data

    def delete_user(self, user_id):
        """Delete user data from database."""
        self.db_client.collection(u'users').document(user_id).delete()
        self.cache.delete(user_id)
        return True

    def cleanup(self):
        """Delete expired users from database."""
        now = int(time())
        docs = self.db_client.collection(u'users').where(u'expires_at', u'<=', now).stream()
        batch = self.db_client.batch()
        counter = 0
        for doc in docs:
            counter = counter + 1
            # Each transaction or batch of writes can write to a maximum of 500 documents.
            # https://cloud.google.com/firestore/quotas#writes_and_transactions
            if counter % 500 == 0:
                batch.commit()
            batch.delete(doc.reference)
        batch.commit()
        LOG.info('Deleted %d documents in %d seconds.', counter, int(time()) - now)
        self.cache.cleanup()
        return True
