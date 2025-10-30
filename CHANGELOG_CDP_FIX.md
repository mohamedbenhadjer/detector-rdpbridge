# Fix: CDP Target Selection for Locator Errors

## Problem
The detector was sometimes sending CDP information for the wrong tab to the Flutter app. This happened specifically on even-numbered sessions because those errors originated from Playwright `Locator` methods rather than `Page` methods.

### Root Cause
- **Page method errors** (e.g., `page.click()`, `page.wait_for_selector()`): The wrapper extracted `url`, `title`, and `debugPort` correctly because `self` was a `Page` object.
- **Locator method errors** (e.g., `locator.click()`): The wrapper couldn't extract context because `self` was a `Locator` object, not a `Page`. This resulted in sending only `{"browser": "chromium"}` without CDP criteria.

### Evidence from User Logs
1. **First request** (room `5MJLfN3BjsGV2UkeXZGp`): `wait_for_load_state` error included full CDP criteria → Flutter connected to "Pixilart" tab ✓
2. **Second request** (room `ofjBZnOw8RZS3bYMuL31`): `Locator.click` error sent only `{"browser":"chromium"}` → Flutter logged "No CDP target criteria provided" and captured wrong window (Brave) ✗
3. **Third request** (room `VptuAJRhw0xADD3Uo3Md`): `wait_for_selector` error included full CDP criteria → Flutter connected correctly ✓

## Solution
Modified `sitecustomize.py` to resolve the `Page` object from `Locator` instances before extracting CDP criteria.

### Changes Made

#### 1. `sitecustomize.py`
- Added `_resolve_page_obj()` helper inside `_wrap_method()` to traverse from `Locator` → `Page`
- Updated both sync and async wrappers to:
  - Resolve page object from both `Page` and `Locator` instances
  - Extract browser info from resolved page's context
  - Pass complete CDP criteria to `trigger_support_request()`

#### 2. `miniagent_ws.py`
- Changed debugPort check from `if debug_port:` to `if debug_port is not None:` to handle edge case where port could be 0

#### 3. Tests
- **Unit test**: `tests/test_locator_error_payload.py` - Captures and verifies payloads from both Page and Locator errors
- **Manual test**: `tests/manual_verification_script.py` - Interactive script to verify Flutter receives correct CDP criteria

#### 4. Documentation
- Updated `README.md` to note that both Page and Locator errors include full CDP criteria
- Added troubleshooting section for "CDP not connecting to correct tab"

## Files Changed
- `sitecustomize.py` - Core fix for resolving Page from Locator
- `miniagent_ws.py` - Hardened debugPort check
- `tests/test_locator_error_payload.py` - New unit test
- `tests/manual_verification_script.py` - New manual verification script
- `README.md` - Updated documentation

## Testing

### Automated Test
```bash
export MINIAGENT_ENABLED=1
export MINIAGENT_TOKEN=your_token
python tests/test_locator_error_payload.py
```

Expected output: Both Page and Locator errors include `debugPort`, `urlContains`, `titleContains`

### Manual Verification with Flutter
```bash
export MINIAGENT_ENABLED=1
export MINIAGENT_TOKEN=your_token
python tests/manual_verification_script.py
```

Watch Flutter logs to confirm:
- Both errors include complete `controlTarget` with `debugPort: 9222`, `urlContains`, `titleContains`
- CDP connects to the correct Pixilart tab for both errors
- No fallback to wrong window/tab

## Expected Behavior After Fix
- **Page errors**: Continue to work as before (already correct)
- **Locator errors**: Now include full CDP criteria like Page errors
- **Flutter**: Always receives `debugPort`, `urlContains`, `titleContains` for accurate tab selection
- **Result**: No more wrong-tab/window capture fallback

## Rollback
If issues arise, revert commits to:
- `sitecustomize.py`: Remove `_resolve_page_obj()` and restore original extraction logic
- `miniagent_ws.py`: Change back to `if debug_port:`

