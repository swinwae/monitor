from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    """标准库命令执行封装,便于测试中替换。"""

    def run(self, args: list[str], timeout: float = 8.0) -> CommandResult:
        try:
            p = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return CommandResult(p.returncode, p.stdout, p.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CommandResult(127, "", str(exc))


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def tail_file(path: str | None, lines: int) -> str:
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        return ""
    with p.open("rb") as f:
        chunk_size = 8192
        f.seek(0, 2)
        pos = f.tell()
        chunks: list[bytes] = []
        newline_count = 0
        while pos > 0 and newline_count <= lines:
            read_size = min(chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
    data = b"".join(reversed(chunks))
    text = data.decode(errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None

