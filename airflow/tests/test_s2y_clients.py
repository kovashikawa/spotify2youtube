"""
Tests for the DAG's token fetch and per-task client construction.

The Firestore call is faked, so nothing here touches a real project, and no
Spotify or YouTube API call is ever made.
"""

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "dags"))

import s2y_clients  # noqa: E402


# --- fake Firestore ---------------------------------------------------------

class FakeDoc:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return self._data


class FakeDocRef:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def collection(self, name):
        return FakeCollection(self.store, f"{self.path}/{name}")

    def get(self):
        return FakeDoc(self.store.data.get(self.path))

    def set(self, data, merge=False):
        self.store.writes.append((self.path, data, merge))
        current = dict(self.store.data.get(self.path) or {}) if merge else {}
        current.update(data)
        self.store.data[self.path] = current


class FakeCollection:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def document(self, name):
        return FakeDocRef(self.store, f"{self.path}/{name}")


class FakeFirestore:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.writes = []

    def collection(self, name):
        return FakeCollection(self, name)


SPOTIFY_PATH = "users/rafael/tokens/spotify"
YOUTUBE_PATH = "users/rafael/tokens/youtube"


@pytest.fixture(autouse=True)
def fake_variables(monkeypatch):
    """Keep Airflow Variable lookups out of the tests."""
    values = {
        "s2y_spotify_client_id": "cid",
        "s2y_spotify_client_secret": "csecret",
        "s2y_firestore_project": "proj",
    }
    monkeypatch.setattr(
        s2y_clients, "get_variable", lambda key, default=None: values.get(key, default)
    )
    return values


# --- token fetch ------------------------------------------------------------

def test_load_spotify_token_reads_json_string():
    token = {"access_token": "AT", "refresh_token": "RT", "expires_at": 9999999999}
    db = FakeFirestore({SPOTIFY_PATH: {"token_info": json.dumps(token)}})

    assert s2y_clients.load_spotify_token(db, "rafael") == token


def test_load_spotify_token_missing_document_raises():
    db = FakeFirestore()
    with pytest.raises(RuntimeError, match="No Spotify token in Firestore"):
        s2y_clients.load_spotify_token(db, "rafael")


def test_load_spotify_token_empty_field_raises():
    db = FakeFirestore({SPOTIFY_PATH: {"something_else": 1}})
    with pytest.raises(RuntimeError, match="no token_info"):
        s2y_clients.load_spotify_token(db, "rafael")


def test_load_youtube_token_reads_json_string():
    info = {"token": "AT", "refresh_token": "RT", "client_id": "cid",
            "client_secret": "csecret"}
    db = FakeFirestore({YOUTUBE_PATH: {"token_json": json.dumps(info)}})

    assert s2y_clients.load_youtube_token(db, "rafael") == info


def test_load_youtube_token_missing_document_raises():
    db = FakeFirestore()
    with pytest.raises(RuntimeError, match="No YouTube token in Firestore"):
        s2y_clients.load_youtube_token(db, "rafael")


# --- Spotify client construction -------------------------------------------

def test_build_spotify_client_uses_token_and_never_touches_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token = {"access_token": "AT", "refresh_token": "RT", "expires_at": 9999999999}
    db = FakeFirestore({SPOTIFY_PATH: {"token_info": json.dumps(token)}})

    sp = s2y_clients.build_spotify_client(db, "rafael")

    assert sp._auth == "AT"
    # a valid token must not be refreshed, so nothing is written back
    assert db.writes == []
    # spotipy must not have written a shared cache file into the worker cwd
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".cache")] == []


def test_build_spotify_client_refreshes_expired_token_and_persists(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    expired = {"access_token": "OLD", "refresh_token": "RT", "expires_at": 1}
    db = FakeFirestore({SPOTIFY_PATH: {"token_info": json.dumps(expired)}})

    refreshed = {"access_token": "NEW", "refresh_token": "RT", "expires_at": 9999999999}

    import spotipy.oauth2 as oauth2

    calls = {}

    def fake_refresh(self, refresh_token):
        calls["refresh_token"] = refresh_token
        return refreshed

    monkeypatch.setattr(oauth2.SpotifyOAuth, "refresh_access_token", fake_refresh)

    sp = s2y_clients.build_spotify_client(db, "rafael")

    assert calls["refresh_token"] == "RT"
    assert sp._auth == "NEW"
    # the refreshed token goes back to Firestore, under this user's path only
    assert len(db.writes) == 1
    path, data, merge = db.writes[0]
    assert path == SPOTIFY_PATH
    assert merge is True
    assert json.loads(data["token_info"]) == refreshed
    # and still nothing on disk
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(".cache")) == []


def test_build_spotify_client_uses_memory_cache_handler(monkeypatch, tmp_path):
    """The cache handler is what keeps two users from sharing one token file."""
    from spotipy.cache_handler import MemoryCacheHandler

    monkeypatch.chdir(tmp_path)
    token = {"access_token": "AT", "refresh_token": "RT", "expires_at": 9999999999}
    db = FakeFirestore({SPOTIFY_PATH: {"token_info": json.dumps(token)}})

    seen = {}
    import spotipy.oauth2 as oauth2
    original_init = oauth2.SpotifyOAuth.__init__

    def spy_init(self, *args, **kwargs):
        seen["cache_handler"] = kwargs.get("cache_handler")
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(oauth2.SpotifyOAuth, "__init__", spy_init)

    s2y_clients.build_spotify_client(db, "rafael")

    assert isinstance(seen["cache_handler"], MemoryCacheHandler)


# --- YouTube client construction -------------------------------------------

def _youtube_info(expiry: str, token: str = "AT") -> dict:
    """
    A stored YouTube blob, shaped like Credentials.to_json() output.

    The expiry field matters: google-auth defaults a missing expiry to now,
    which makes the credentials report expired straight away.
    """
    return {
        "token": token,
        "refresh_token": "RT",
        "client_id": "cid",
        "client_secret": "csecret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": s2y_clients.YOUTUBE_SCOPES,
        "expiry": expiry,
    }


@pytest.fixture(autouse=True)
def no_token_endpoint_calls(monkeypatch):
    """Fail loudly instead of reaching Google if a refresh is not stubbed."""
    from google.oauth2.credentials import Credentials

    def forbidden(self, request):
        raise AssertionError("unexpected network refresh against Google")

    monkeypatch.setattr(Credentials, "refresh", forbidden)


def test_build_youtube_client_constructs_from_firestore_token(monkeypatch):
    info = _youtube_info(expiry="2999-01-01T00:00:00")
    db = FakeFirestore({YOUTUBE_PATH: {"token_json": json.dumps(info)}})

    built = {}

    def fake_build(serviceName, version, credentials=None, **kwargs):
        built["service"] = (serviceName, version)
        built["token"] = credentials.token
        built["refresh_token"] = credentials.refresh_token
        return "youtube-service"

    import googleapiclient.discovery as discovery
    monkeypatch.setattr(discovery, "build", fake_build)

    service = s2y_clients.build_youtube_client(db, "rafael")

    assert service == "youtube-service"
    assert built["service"] == ("youtube", "v3")
    assert built["token"] == "AT"
    assert built["refresh_token"] == "RT"
    # an unexpired token is not refreshed, so nothing is written back
    assert db.writes == []


def test_build_youtube_client_refreshes_expired_and_persists(monkeypatch):
    info = _youtube_info(expiry="2000-01-01T00:00:00", token="OLD")
    db = FakeFirestore({YOUTUBE_PATH: {"token_json": json.dumps(info)}})

    import googleapiclient.discovery as discovery
    monkeypatch.setattr(discovery, "build", lambda *a, **k: "youtube-service")

    from google.oauth2.credentials import Credentials

    refreshed = {}

    def fake_refresh(self, request):
        refreshed["called"] = True
        self.token = "NEW"

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)

    s2y_clients.build_youtube_client(db, "rafael")

    assert refreshed["called"] is True
    assert len(db.writes) == 1
    path, data, merge = db.writes[0]
    assert path == YOUTUBE_PATH
    assert merge is True
    assert json.loads(data["token_json"])["token"] == "NEW"


# --- no client ever crosses a task boundary --------------------------------

def test_dag_tasks_do_not_return_clients():
    """
    The original bug was authenticate() returning a spotipy.Spotify through
    XCom. Guard the shape: the DAG must expose no task named 'authenticate',
    and resolve_user must be annotated to return a plain string.
    """
    import inspect

    dag_source = (
        pathlib.Path(__file__).parents[1] / "dags" / "spotify_youtube_sync_dag.py"
    ).read_text()

    assert "def authenticate(" not in dag_source
    assert "def resolve_user() -> str:" in dag_source
    assert "return sp" not in dag_source
    # search_youtube must be called with a client argument
    assert "search_youtube(youtube," in dag_source
    assert inspect is not None
