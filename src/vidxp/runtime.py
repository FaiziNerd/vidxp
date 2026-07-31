from __future__ import annotations

import platform
import hashlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock, RLock
from time import monotonic, sleep
from typing import Any, Callable, Iterator
from pathlib import Path

from vidxp.application_models import RuntimeProfile
from vidxp.model_contracts import (
    ArtifactSpec,
    ModelArtifactDownloadError,
    ModelArtifactUnavailableError,
    ModelKey,
    ModelSpec,
)
from vidxp.settings import VidXPSettings


class RuntimeBackendUnavailableError(RuntimeError):
    """Raised when an explicitly requested compute backend cannot be used."""


class _ModelDownloadVerificationError(RuntimeError):
    """Raised internally when a completed transfer is missing pinned weights."""


_MODEL_DOWNLOAD_ATTEMPTS = 3
_DOWNLOAD_HEARTBEAT_SECONDS = 5.0
_MINIMUM_PROGRESS_BYTES = 1024 * 1024


def _download_failure_reason(exc: Exception) -> str:
    if isinstance(exc, _ModelDownloadVerificationError):
        return "artifact verification failed"
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return f"HTTP {status} {type(exc).__name__}"
    return type(exc).__name__


def _download_failure_retryable(
    exc: Exception,
    *,
    hash_mismatch_is_retryable: bool = False,
) -> bool | None:
    if isinstance(exc, _ModelDownloadVerificationError):
        return True
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status in {408, 409, 425, 429} or status >= 500
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    try:
        import httpx
    except ModuleNotFoundError:
        pass
    else:
        if isinstance(exc, httpx.TransportError):
            return True
    try:
        from requests import exceptions as requests_exceptions
    except ModuleNotFoundError:
        pass
    else:
        if isinstance(
            exc,
            (requests_exceptions.ConnectionError, requests_exceptions.Timeout),
        ):
            return True
    if hash_mismatch_is_retryable and isinstance(exc, ValueError):
        return True
    if isinstance(exc, OSError):
        return False
    if type(exc).__module__.startswith(("huggingface_hub", "pooch")):
        return False
    return None


def _torch_accelerators() -> tuple[bool, bool]:
    try:
        import torch
    except ModuleNotFoundError:
        return False, False
    mps = bool(
        getattr(torch.backends, "mps", None)
        and torch.backends.mps.is_available()
    )
    return mps, bool(torch.cuda.is_available())


def resolve_backends(requested: str) -> RuntimeProfile:
    mps_available, cuda_available = _torch_accelerators()
    normalized = requested.lower()
    if normalized == "auto":
        torch_device = "cpu"
    elif normalized == "mps":
        if not mps_available:
            raise RuntimeBackendUnavailableError(
                "MPS was requested but is unavailable."
            )
        torch_device = "mps"
    elif normalized.startswith("cuda"):
        if not cuda_available:
            raise RuntimeBackendUnavailableError(
                "CUDA was requested but is unavailable."
            )
        if ":" in normalized:
            import torch

            index = int(normalized.split(":", 1)[1])
            if index >= torch.cuda.device_count():
                raise RuntimeBackendUnavailableError(
                    f"CUDA device {index} was requested but only "
                    f"{torch.cuda.device_count()} device(s) are available."
                )
        torch_device = normalized
    elif normalized == "cpu":
        torch_device = "cpu"
    else:
        raise RuntimeBackendUnavailableError(
            f"Unsupported runtime backend: {requested!r}."
        )
    return RuntimeProfile(
        requested=normalized,
        torch_device=torch_device,
        transcription_device=(
            normalized if normalized.startswith("cuda") else "cpu"
        ),
        mps_available=mps_available,
        cuda_available=cuda_available,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ResourceScheduler:
    """Bound concurrent model work without owning workflow state."""

    def __init__(
        self,
        *,
        indexing_slots: int,
        inference_slots: int,
    ) -> None:
        self._indexing = BoundedSemaphore(indexing_slots)
        self._inference = BoundedSemaphore(inference_slots)

    @contextmanager
    def indexing(self) -> Iterator[None]:
        with self._indexing:
            yield

    @contextmanager
    def inference(self) -> Iterator[None]:
        with self._inference:
            yield


class ModelRuntime:
    """One injected model cache and backend resolver for all capabilities."""

    def __init__(
        self,
        settings: VidXPSettings,
        *,
        allowed_specs: tuple[ModelSpec | ArtifactSpec, ...] = (),
    ) -> None:
        self.settings = settings
        self._allowed_specs = frozenset(allowed_specs)
        self.backends = resolve_backends(settings.runtime_backend)
        self.scheduler = ResourceScheduler(
            indexing_slots=settings.max_concurrent_indexing,
            inference_slots=settings.max_concurrent_inference,
        )
        self._resources: OrderedDict[ModelKey, Any] = OrderedDict()
        self._resolved_models: dict[str, dict[str, Any]] = {}
        self._compute_precision: dict[str, str] = {}
        self._load_locks: dict[ModelKey, Lock] = {}
        self._lock = RLock()

    @property
    def model_cache(self) -> Path:
        return self.settings.model_cache

    @property
    def cpu_thread_budget(self) -> int:
        return self.settings.cpu_thread_budget

    def _configure_cpu_threads(self) -> None:
        try:
            import torch
        except ModuleNotFoundError:
            pass
        else:
            torch.set_num_threads(self.cpu_thread_budget)
        try:
            import cv2
        except ModuleNotFoundError:
            pass
        else:
            cv2.setNumThreads(self.cpu_thread_budget)

    def device_for(self, capability: str) -> str:
        if capability == "dialogue.transcription":
            return self.backends.transcription_device
        if capability == "actor":
            return self.backends.actor_device
        return self.backends.torch_device

    @staticmethod
    def _download_snapshot(
        spec: ModelSpec,
        *,
        cache: Path,
        progress: Callable[[dict[str, Any]], None] | None,
    ) -> Path:
        from huggingface_hub import constants, snapshot_download
        from tqdm.auto import tqdm

        # Xet can remain parked at zero bytes without surfacing an error.
        # The regular HTTP path has bounded read timeouts and reports bytes
        # through tqdm, which is required for durable preparation progress.
        constants.HF_HUB_DISABLE_XET = True
        state_lock = Lock()
        state: dict[str, Any] = {
            "current": 0,
            "total": spec.download_size_bytes,
            "message": f"Connecting to download {spec.model_id}.",
        }

        class ReportingTqdm(tqdm):
            def display(self, msg=None, pos=None) -> None:
                return None

            def update(self, n=1):
                result = super().update(n)
                if self.unit == "B":
                    with state_lock:
                        previous = getattr(self, "_vidxp_reported_bytes", 0)
                        current = int(self.n)
                        self._vidxp_reported_bytes = current
                        state["current"] = min(
                            spec.download_size_bytes,
                            int(state["current"]) + max(0, current - previous),
                        )
                        state["message"] = f"Downloading {spec.model_id}."
                return result

        def download() -> str:
            snapshot = Path(
                snapshot_download(
                    repo_id=spec.model_id,
                    revision=spec.revision,
                    cache_dir=str(cache),
                    local_files_only=False,
                    tqdm_class=ReportingTqdm,
                )
            )
            weights = snapshot / spec.weights_file
            if (
                not weights.is_file()
                or _sha256(weights) != spec.weights_sha256
            ):
                raise _ModelDownloadVerificationError
            return str(snapshot)

        reported_at = 0.0
        reported_current = -1
        progress_step = max(
            _MINIMUM_PROGRESS_BYTES,
            spec.download_size_bytes // 100,
        )

        def report(*, force: bool = False):
            nonlocal reported_at, reported_current
            if progress is None:
                return
            now = monotonic()
            with state_lock:
                event = dict(state)
            current = int(event["current"])
            advanced = current - reported_current >= progress_step
            heartbeat = now - reported_at >= _DOWNLOAD_HEARTBEAT_SECONDS
            if not force and reported_current >= 0 and not advanced and not heartbeat:
                return
            progress(
                {
                    "state": "preparing",
                    "stage": "downloading_model",
                    **event,
                }
            )
            reported_at = now
            reported_current = current

        last_error: Exception | None = None
        last_retryable = False
        attempts = 0
        for attempt in range(1, _MODEL_DOWNLOAD_ATTEMPTS + 1):
            attempts = attempt
            with state_lock:
                state["message"] = (
                    f"Connecting to download {spec.model_id}."
                    if attempt == 1
                    else (
                        f"Retrying download of {spec.model_id} "
                        f"(attempt {attempt} of {_MODEL_DOWNLOAD_ATTEMPTS})."
                    )
                )
            report(force=True)
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(download)
                    while True:
                        try:
                            snapshot = future.result(timeout=0.5)
                            break
                        except FutureTimeout:
                            report()
            except Exception as exc:
                last_error = exc
                retryable = _download_failure_retryable(exc)
                if retryable is None:
                    raise
                last_retryable = retryable
                if (
                    attempt >= _MODEL_DOWNLOAD_ATTEMPTS
                    or not retryable
                ):
                    break
                with state_lock:
                    state["message"] = (
                        f"Download interrupted for {spec.model_id}; cached "
                        "partial files will be resumed."
                    )
                report(force=True)
                sleep(2 ** (attempt - 1))
                continue
            with state_lock:
                state["current"] = spec.download_size_bytes
                state["message"] = f"Downloaded {spec.model_id}."
            report(force=True)
            return Path(snapshot)

        assert last_error is not None
        raise ModelArtifactDownloadError(
            spec.capability,
            spec.model_id,
            attempts=attempts,
            reason=_download_failure_reason(last_error),
            resumable=True,
            retryable=last_retryable,
        ) from last_error

    def resolve_model(
        self,
        spec: ModelSpec,
        *,
        download: bool = False,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> Path:
        if spec not in self._allowed_specs:
            raise ModelArtifactUnavailableError(spec.capability)
        from huggingface_hub import snapshot_download

        try:
            snapshot: Path | None
            try:
                local_snapshot = Path(
                    snapshot_download(
                        repo_id=spec.model_id,
                        revision=spec.revision,
                        cache_dir=str(self.settings.model_cache),
                        local_files_only=True,
                    )
                )
                local_weights = local_snapshot / spec.weights_file
                snapshot = (
                    local_snapshot
                    if local_weights.is_file()
                    and _sha256(local_weights) == spec.weights_sha256
                    else None
                )
            except Exception:
                snapshot = None
            if snapshot is None:
                if not download or not self.settings.allow_model_downloads:
                    raise ModelArtifactUnavailableError(spec.capability)
                snapshot = self._download_snapshot(
                    spec,
                    cache=self.settings.model_cache,
                    progress=progress,
                )
        except (ModelArtifactDownloadError, ModelArtifactUnavailableError):
            raise
        except Exception as exc:
            raise ModelArtifactUnavailableError(spec.capability) from exc
        with self._lock:
            self._resolved_models[spec.capability] = spec.identity(cached=True)
        return snapshot

    def resolve_artifact(
        self,
        spec: ArtifactSpec,
        *,
        download: bool = False,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> Path:
        if spec not in self._allowed_specs:
            raise ModelArtifactUnavailableError(spec.capability)
        try:
            destination = self.settings.model_cache / spec.provider
            path = destination / spec.filename
            if not path.is_file() or _sha256(path) != spec.sha256:
                if not download or not self.settings.allow_model_downloads:
                    raise ModelArtifactUnavailableError(spec.capability)
                if progress is not None:
                    progress(
                        {
                            "state": "preparing",
                            "stage": "downloading_model",
                            "message": f"Downloading {spec.model_id}.",
                            "current": 0,
                            "total": spec.download_size_bytes,
                        }
                    )
                import pooch

                last_error = None
                for attempt in range(1, _MODEL_DOWNLOAD_ATTEMPTS + 1):
                    try:
                        resolved = Path(
                            pooch.retrieve(
                                url=spec.url,
                                known_hash=f"sha256:{spec.sha256}",
                                fname=spec.filename,
                                path=destination,
                                progressbar=False,
                            )
                        )
                        break
                    except Exception as exc:
                        last_error = exc
                        retryable = _download_failure_retryable(
                            exc,
                            hash_mismatch_is_retryable=True,
                        )
                        if retryable is None:
                            raise
                        if (
                            attempt >= _MODEL_DOWNLOAD_ATTEMPTS
                            or not retryable
                        ):
                            raise ModelArtifactDownloadError(
                                spec.capability,
                                spec.model_id,
                                attempts=attempt,
                                reason=_download_failure_reason(exc),
                                resumable=False,
                                retryable=retryable,
                            ) from exc
                        if progress is not None:
                            progress(
                                {
                                    "state": "preparing",
                                    "stage": "downloading_model",
                                    "message": (
                                        f"Download interrupted for "
                                        f"{spec.model_id}; retrying attempt "
                                        f"{attempt + 1} of "
                                        f"{_MODEL_DOWNLOAD_ATTEMPTS}. This "
                                        "file will restart from zero."
                                    ),
                                    "current": 0,
                                    "total": spec.download_size_bytes,
                                }
                            )
                        sleep(2 ** (attempt - 1))
                else:
                    assert last_error is not None
                    raise last_error
            else:
                resolved = path
            if not resolved.is_file() or _sha256(resolved) != spec.sha256:
                raise ModelArtifactUnavailableError(spec.capability)
            if progress is not None:
                progress(
                    {
                        "state": "preparing",
                        "stage": "downloading_model",
                        "message": f"Verified {spec.model_id}.",
                        "current": spec.download_size_bytes,
                        "total": spec.download_size_bytes,
                    }
                )
        except (ModelArtifactDownloadError, ModelArtifactUnavailableError):
            raise
        except Exception as exc:
            raise ModelArtifactUnavailableError(spec.capability) from exc
        with self._lock:
            self._resolved_models[spec.capability] = spec.identity(cached=True)
        return resolved

    def record_compute_precision(
        self,
        capability: str,
        precision: str,
    ) -> None:
        with self._lock:
            self._compute_precision[capability] = precision

    def get_or_load(
        self,
        key: ModelKey,
        loader: Callable[[], Any],
    ) -> Any:
        with self._lock:
            if key in self._resources:
                resource = self._resources.pop(key)
                self._resources[key] = resource
                return resource
            key_lock = self._load_locks.setdefault(key, Lock())

        with key_lock:
            with self._lock:
                if key in self._resources:
                    resource = self._resources.pop(key)
                    self._resources[key] = resource
                    return resource
            self._configure_cpu_threads()
            resource = loader()
            with self._lock:
                existing = self._resources.pop(key, None)
                if existing is not None:
                    return existing
                self._resources[key] = resource
                while len(self._resources) > self.settings.max_loaded_models:
                    self._resources.popitem(last=False)
                self._load_locks.pop(key, None)
                return resource

    def clear(self) -> None:
        with self._lock:
            self._resources.clear()
            self._load_locks.clear()
        try:
            import torch
        except ModuleNotFoundError:
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if (
            getattr(torch.backends, "mps", None)
            and torch.backends.mps.is_available()
        ):
            torch.mps.empty_cache()

    def describe(self) -> dict[str, Any]:
        return {
            "platform": platform.system().lower(),
            "architecture": platform.machine().lower(),
            **self.backends.model_dump(mode="json"),
            "model_cache": str(self.settings.model_cache),
            "allow_model_downloads": self.settings.allow_model_downloads,
            "limits": {
                "max_loaded_models": self.settings.max_loaded_models,
                "max_concurrent_indexing": (
                    self.settings.max_concurrent_indexing
                ),
                "max_concurrent_inference": (
                    self.settings.max_concurrent_inference
                ),
                "cpu_thread_budget": self.settings.cpu_thread_budget,
            },
            "resolved_models": dict(self._resolved_models),
            "compute_precision": dict(self._compute_precision),
        }
