# Publication media validation

This is an unreleased engineering change after candidate 0.3.1. That frozen candidate and its archives remain unchanged. Its mobile screenshot contains JPEG bytes under a `.png` filename; the existing System Lab revision prepared for publication uses the same bytes under `.jpg`. A future software candidate must use correctly named media in its own version namespace.

The publisher checks the selected release screenshot and supported raster files in the current candidate's media directory, including nested and unselected mobile captures. Reused selected historical images are checked. Unrelated historical media is preserved. The guard matches filename extension with PNG, JPEG or single-frame WebP encoding and checks bounded container framing. PNG chunk checksums and required image headers are checked. It does not decompress pixels or establish visual correctness, rights, source provenance or operational acceptance. Actual browser captures and visual review remain separate release gates.

The guard uses the Python standard library. It reads at most 32 MiB plus one byte per raster and refuses unsupported encodings, malformed containers, filename mismatches and excessive media collections. Publication permissions, current-source checks, secret scans and approval requirements remain unchanged.

Run the focused regression checks with `PYTHONPATH=backend`:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_publication_raster_guard.py tests/test_publication_material.py tests/test_candidate_publication.py tests/test_ci_publication_adversarial.py tests/test_release_tools.py
```

The tiny artificial raster fixtures belong only to isolated software tests. They are not product screenshots, operational records or training evidence. The encoding formats are documented by the [W3C PNG specification](https://www.w3.org/TR/png-3/), [WebP container documentation](https://developers.google.com/speed/webp/docs/riff_container) and [ITU-T T.81 JPEG specification](https://www.w3.org/Graphics/JPEG/itu-t81.pdf).
