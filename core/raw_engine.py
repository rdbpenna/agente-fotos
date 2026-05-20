from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


RAW_EXTENSIONS = {
    ".cr3", ".cr2", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf"
}


class DarktableNotFoundError(RuntimeError):
    pass


class RawEngine:
    def __init__(self, darktable_cli_path: str | None = None):
        self.darktable_cli = self._find_darktable_cli(darktable_cli_path)

    def _find_darktable_cli(self, custom_path: str | None = None) -> str:
        candidates: list[str] = []

        if custom_path:
            candidates.append(custom_path)

        env_path = os.environ.get("DARKTABLE_CLI")
        if env_path:
            candidates.append(env_path)

        found_in_path = shutil.which("darktable-cli")
        if found_in_path:
            candidates.append(found_in_path)

        candidates.extend([
            r"C:\Program Files\darktable\bin\darktable-cli.exe",
            r"C:\Program Files\darktable\darktable-cli.exe",
            r"C:\Program Files (x86)\darktable\bin\darktable-cli.exe",
        ])

        for candidate in candidates:
            p = Path(candidate)
            if p.exists() and p.is_file():
                return str(p)

        raise DarktableNotFoundError(
            "darktable-cli não foi encontrado. Instale o Darktable ou configure DARKTABLE_CLI."
        )

    @staticmethod
    def is_raw_file(path: str | Path) -> bool:
        return Path(path).suffix.lower() in RAW_EXTENSIONS

    def reveal_to_jpg(
        self,
        input_file: str | Path,
        output_file: str | Path,
        overwrite: bool = True,
    ) -> Path:
        input_file = Path(input_file).resolve()
        output_file = Path(output_file).resolve()

        if not input_file.exists():
            raise FileNotFoundError(f"Arquivo RAW não encontrado: {input_file}")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        if output_file.exists() and overwrite:
            output_file.unlink()

        if output_file.exists() and not overwrite:
            return output_file

        cmd = [
            self.darktable_cli,
            str(input_file),
            str(output_file),
            "--core",
            "--conf",
            "plugins/imageio/format/jpeg/quality=95",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            cwd=str(output_file.parent),
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        logs = "\n".join(x for x in [stdout, stderr] if x)

        if result.returncode != 0:
            raise RuntimeError(
                f"Erro ao revelar RAW/CR3 com darktable-cli.\n"
                f"Arquivo: {input_file}\n"
                f"Saída: {output_file}\n"
                f"Comando: {' '.join(cmd)}\n"
                f"Logs:\n{logs}"
            )

        if output_file.exists():
            return output_file

        # Procura arquivos criados perto da saída desejada
        possible_files = list(output_file.parent.glob(output_file.stem + "*"))
        possible_files += list(output_file.parent.glob("*.jpg"))
        possible_files += list(output_file.parent.glob("*.jpeg"))

        if possible_files:
            newest = max(possible_files, key=lambda p: p.stat().st_mtime)
            if newest.exists() and newest.stat().st_size > 0:
                if newest != output_file:
                    shutil.copy2(newest, output_file)
                return output_file

        raise RuntimeError(
            f"O darktable-cli executou, mas não criou o JPG esperado.\n"
            f"Arquivo: {input_file}\n"
            f"Saída esperada: {output_file}\n"
            f"Comando: {' '.join(cmd)}\n"
            f"Logs:\n{logs if logs else '(sem logs)'}"
        )
