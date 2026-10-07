from pathlib import Path

from w11cursor.render.cairo_backend import ensure_windows_cairo_path


class Loader:
    def __init__(self):
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        return object()


def test_preloads_msys2_dll_by_full_path(tmp_path: Path):
    (tmp_path / "libcairo-2.dll").write_bytes(b"")
    env, load = {}, Loader()
    got = ensure_windows_cairo_path(env, True, tmp_path, load)
    assert got == str(tmp_path / "libcairo-2.dll")
    assert load.calls == [got]                      # full path, not bare name
    assert env["CAIROCFFI_DLL_DIRECTORIES"] == str(tmp_path)


def test_user_folder_wins_over_default(tmp_path: Path):
    user, default = tmp_path / "user", tmp_path / "default"
    for d in (user, default):
        d.mkdir()
        (d / "libcairo-2.dll").write_bytes(b"")
    env, load = {"CAIROCFFI_DLL_DIRECTORIES": f"X:\\nope;{user}"}, Loader()
    assert ensure_windows_cairo_path(env, True, default, load) == str(user / "libcairo-2.dll")
    assert len(load.calls) == 1


def test_noop_without_dll_or_off_windows(tmp_path: Path):
    env, load = {}, Loader()
    assert ensure_windows_cairo_path(env, True, tmp_path, load) is None and env == {} and not load.calls
    (tmp_path / "libcairo-2.dll").write_bytes(b"")
    assert ensure_windows_cairo_path(env, False, tmp_path, load) is None and not load.calls
