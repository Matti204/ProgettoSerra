"""Lock di processo rilasciato dal sistema operativo anche dopo un crash."""

import os


class InstanceLock:
    def __init__(self, path):
        self._file = open(path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if self._file.seek(0, 2) == 0:
                    self._file.write(b"0")
                    self._file.flush()
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._file.close()
            raise RuntimeError("Un'altra istanza usa questa DATA_DIR. Arrestarla prima di avviare il server.") from exc

    def close(self):
        if not self._file.closed:
            if os.name == "nt":
                import msvcrt
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file, fcntl.LOCK_UN)
            self._file.close()
