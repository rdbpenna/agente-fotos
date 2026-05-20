"""
Detector de fotos duplicadas ou muito semelhantes.

Usa perceptual hashing (pHash) para comparar imagens:
  • Fotos idênticas → duplicata exata
  • Fotos muito semelhantes → possível duplicata (ângulo ligeiramente diferente)
  • Fotos diferentes → mantém ambas

Gera relatório das duplicatas encontradas e pode mover para pasta separada.
"""

import os
import cv2
import numpy as np


class DuplicateDetector:
    """Detecta fotos duplicadas ou muito semelhantes."""

    def __init__(self, threshold: int = 10):
        """
        Args:
            threshold: distância máxima de Hamming para considerar duplicata.
                       0 = idênticas, 10 = muito semelhantes (padrão),
                       20 = moderadamente semelhantes.
        """
        self.threshold = threshold

    def find_duplicates(self, image_paths: list[str],
                        progress_callback=None) -> list[dict]:
        """
        Analisa lista de imagens e retorna grupos de duplicatas.

        Args:
            image_paths: lista de caminhos completos.
            progress_callback: função(msg, pct) opcional.

        Returns:
            Lista de dicts: {"original": path, "duplicates": [paths],
                             "distances": [int]}
        """
        if len(image_paths) < 2:
            return []

        # Calcula hash de cada imagem
        hashes: list[tuple[str, np.ndarray | None]] = []
        for i, path in enumerate(image_paths):
            h = self._compute_phash(path)
            hashes.append((path, h))
            if progress_callback:
                progress_callback(
                    f"Calculando hash: {os.path.basename(path)}",
                    (i + 1) / len(image_paths) * 0.5,
                )

        # Compara todos os pares
        already_duplicate = set()
        groups = []

        for i in range(len(hashes)):
            path_i, hash_i = hashes[i]
            if hash_i is None or path_i in already_duplicate:
                continue

            group_dupes = []
            group_dists = []

            for j in range(i + 1, len(hashes)):
                path_j, hash_j = hashes[j]
                if hash_j is None or path_j in already_duplicate:
                    continue

                dist = self._hamming_distance(hash_i, hash_j)
                if dist <= self.threshold:
                    group_dupes.append(path_j)
                    group_dists.append(dist)
                    already_duplicate.add(path_j)

            if group_dupes:
                groups.append({
                    "original": path_i,
                    "duplicates": group_dupes,
                    "distances": group_dists,
                })

            if progress_callback:
                progress_callback(
                    f"Comparando imagens...",
                    0.5 + (i + 1) / len(hashes) * 0.5,
                )

        return groups

    def move_duplicates(self, groups: list[dict], dest_folder: str) -> int:
        """
        Move duplicatas para uma pasta separada.

        Returns:
            Número de arquivos movidos.
        """
        os.makedirs(dest_folder, exist_ok=True)
        moved = 0

        for group in groups:
            for dup_path in group["duplicates"]:
                filename = os.path.basename(dup_path)
                dest = os.path.join(dest_folder, filename)

                # Evita sobrescrever
                if os.path.exists(dest):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(dest_folder, f"{base}_dup{counter}{ext}")
                        counter += 1

                try:
                    os.rename(dup_path, dest)
                    moved += 1
                except OSError:
                    # Se rename falha (disco diferente), copia e remove
                    import shutil
                    shutil.move(dup_path, dest)
                    moved += 1

        return moved

    @staticmethod
    def _compute_phash(image_path: str, hash_size: int = 16) -> np.ndarray | None:
        """
        Calcula perceptual hash (pHash) da imagem.

        Processo:
          1. Reduz para 32×32 em escala de cinza
          2. Aplica DCT (Discrete Cosine Transform)
          3. Usa os coeficientes de baixa frequência
          4. Binariza pelo valor mediano
        """
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None

        # Reduz tamanho
        resized = cv2.resize(img, (hash_size * 2, hash_size * 2),
                             interpolation=cv2.INTER_AREA)
        resized = resized.astype(np.float32)

        # DCT
        dct = cv2.dct(resized)

        # Usa quadrante superior esquerdo (baixas frequências)
        dct_low = dct[:hash_size, :hash_size]

        # Binariza pelo mediano
        median = np.median(dct_low)
        hash_bits = (dct_low > median).astype(np.uint8)

        return hash_bits.flatten()

    @staticmethod
    def _hamming_distance(hash1: np.ndarray, hash2: np.ndarray) -> int:
        """Distância de Hamming entre dois hashes."""
        return int(np.sum(hash1 != hash2))
