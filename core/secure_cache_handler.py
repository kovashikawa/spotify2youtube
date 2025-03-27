import os
import json
from pathlib import Path
from spotipy.cache_handler import CacheHandler

class SecureCacheFileHandler(CacheHandler):
    """A secure cache handler that sets proper file permissions (600) for the auth token cache file."""
    
    def __init__(self, cache_path=None):
        """
        Parameters:
            cache_path: Path to the cache file
        """
        self.cache_path = cache_path

    def get_cached_token(self):
        """Get the cached token from the file."""
        if not self.cache_path:
            return None

        try:
            with open(self.cache_path, 'r') as f:
                cached_token = json.load(f)
                return cached_token
        except (IOError, json.JSONDecodeError):
            return None

    def save_token_to_cache(self, token_info):
        """Save the token to the cache file with secure permissions."""
        if not self.cache_path:
            return

        # Ensure the directory exists with proper permissions
        cache_dir = Path(self.cache_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(cache_dir, 0o700)  # rwx------

        # Write the token to the file
        with open(self.cache_path, 'w') as f:
            json.dump(token_info, f)
        
        # Set secure file permissions (600)
        os.chmod(self.cache_path, 0o600)  # rw------- 