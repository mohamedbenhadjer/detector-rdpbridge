# sitecustomize.py
# Forces Chromium to keep rendering/animating when backgrounded/occluded.

DEFAULT_CHROMIUM_ARGS = [
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
]

def _patch_playwright():
    try:
        from playwright.sync_api import BrowserType  # type: ignore
    except Exception:
        return

    _orig_launch = BrowserType.launch
    _orig_launch_pctx = getattr(BrowserType, "launch_persistent_context", None)

    def _merge_args(kwargs):
        user_args = kwargs.get("args") or []
        kwargs["args"] = list(user_args) + [a for a in DEFAULT_CHROMIUM_ARGS if a not in user_args]

    def _launch_with_flags(self, *args, **kwargs):
        if getattr(self, "name", "") == "chromium":
            _merge_args(kwargs)
        return _orig_launch(self, *args, **kwargs)

    BrowserType.launch = _launch_with_flags  # type: ignore[attr-defined]

    if callable(_orig_launch_pctx):
        def _launch_pctx_with_flags(self, user_data_dir, *args, **kwargs):
            if getattr(self, "name", "") == "chromium":
                _merge_args(kwargs)
            return _orig_launch_pctx(self, user_data_dir, *args, **kwargs)
        BrowserType.launch_persistent_context = _launch_pctx_with_flags  # type: ignore[attr-defined]

_patch_playwright()
