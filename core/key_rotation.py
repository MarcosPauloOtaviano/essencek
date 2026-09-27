"""Retire a previous signing key even when a serverless process stays warm."""
import time


class ExpiringFallbackKeys(list):
    def __init__(self, configured_keys, previous_key, valid_until):
        super().__init__(configured_keys)
        self.configured_keys = tuple(configured_keys)
        self.previous_key = previous_key
        self.valid_until = valid_until

    def _active_keys(self):
        if self.previous_key and time.time() < self.valid_until:
            return (*self.configured_keys, self.previous_key)
        return self.configured_keys

    def __getitem__(self, index):
        return self._active_keys()[index]

    def __iter__(self):
        return iter(self._active_keys())

    def __len__(self):
        return len(self._active_keys())
