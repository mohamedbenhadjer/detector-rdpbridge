import sys

with open("sitecustomize.py", "r") as f:
    content = f.read()

# Replace sys.exit
old_exit = """# Only activate if explicitly enabled
if os.environ.get("MINIAGENT_ENABLED", "1") != "1":
    sys.exit(0)"""

new_exit = """# Only activate if explicitly enabled
_IS_MINIAGENT_ENABLED = os.environ.get("MINIAGENT_ENABLED", "1") == "1"
if not _IS_MINIAGENT_ENABLED:
    # We still define NeedsAgentInterventionError so imports don't fail,
    # but we will skip starting servers or intercepting Playwright later.
    pass"""

content = content.replace(old_exit, new_exit)

old_activate = """# Activate interception on module import
try:
    _intercept_playwright()
except Exception as e:
    logger.error(f"Failed to intercept Playwright: {e}", exc_info=True)

# Start HTTP resume server (if enabled)
try:
    _start_resume_http_server()
except Exception as e:
    logger.error(f"Failed to start resume HTTP server: {e}")

def _handle_exception(exc_type, exc_value, exc_traceback):
    \"\"\"Global exception hook to catch NeedsAgentInterventionError.\"\"\"
    
    if issubclass(exc_type, NeedsAgentInterventionError) and not getattr(exc_value, "_miniagent_handled", False):
        try:
            from miniagent_ws import get_support_manager
            manager = get_support_manager()
            if manager:
                # Get context from last active page
                ctx = _get_support_context()
                
                # Use last failure selectors if available
                global _last_failure_selectors
                success_selector, failure_selector = _last_failure_selectors
                
                manager.trigger_support_request(
                    reason=exc_type.__name__,
                    details=str(exc_value),
                    browser=ctx["browser"],
                    debug_port=ctx["debug_port"],
                    url=ctx["url"],
                    title=ctx["title"],
                    page_id=ctx["page_id"],
                    resume_endpoint=ctx["resume_endpoint"],
                    success_selector=success_selector,
                    failure_selector=failure_selector,
                    cdp_target_id=ctx["cdp_target_id"]
                )
                
                # Handle based on mode (hold/swallow for NeedsAgentInterventionError)
                if _MODE == "hold":
                    # Get page_obj from weakref if possible
                    page_obj = None
                    if _last_active_page_ref:
                        try:
                            page_obj = _last_active_page_ref()
                        except Exception as e:
                            logger.debug(f"Error resolving last active page reference: {e}")
                            
                    _park_until_resume(exc_type.__name__, str(exc_value), page_obj)
                    # Don't call original excepthook - we handled it
                    return
                if _MODE == "swallow":
                    # Don't call original excepthook - suppress the error
                    return
        except Exception as e:
            # Don't let our hook crash the app
            logger.error(f"Exception in global hook: {e}")
            pass
    
    # For all other cases, call the original excepthook (prints traceback and exits)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = _handle_exception"""

new_activate = """def _handle_exception(exc_type, exc_value, exc_traceback):
    \"\"\"Global exception hook to catch NeedsAgentInterventionError.\"\"\"
    
    if issubclass(exc_type, NeedsAgentInterventionError) and not getattr(exc_value, "_miniagent_handled", False):
        try:
            from miniagent_ws import get_support_manager
            manager = get_support_manager()
            if manager:
                # Get context from last active page
                ctx = _get_support_context()
                
                # Use last failure selectors if available
                global _last_failure_selectors
                success_selector, failure_selector = _last_failure_selectors
                
                manager.trigger_support_request(
                    reason=exc_type.__name__,
                    details=str(exc_value),
                    browser=ctx["browser"],
                    debug_port=ctx["debug_port"],
                    url=ctx["url"],
                    title=ctx["title"],
                    page_id=ctx["page_id"],
                    resume_endpoint=ctx["resume_endpoint"],
                    success_selector=success_selector,
                    failure_selector=failure_selector,
                    cdp_target_id=ctx["cdp_target_id"]
                )
                
                # Handle based on mode (hold/swallow for NeedsAgentInterventionError)
                if _MODE == "hold":
                    # Get page_obj from weakref if possible
                    page_obj = None
                    if _last_active_page_ref:
                        try:
                            page_obj = _last_active_page_ref()
                        except Exception as e:
                            logger.debug(f"Error resolving last active page reference: {e}")
                            
                    _park_until_resume(exc_type.__name__, str(exc_value), page_obj)
                    # Don't call original excepthook - we handled it
                    return
                if _MODE == "swallow":
                    # Don't call original excepthook - suppress the error
                    return
        except Exception as e:
            # Don't let our hook crash the app
            logger.error(f"Exception in global hook: {e}")
            pass
    
    # For all other cases, call the original excepthook (prints traceback and exits)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


if _IS_MINIAGENT_ENABLED:
    # Activate interception on module import
    try:
        _intercept_playwright()
    except Exception as e:
        logger.error(f"Failed to intercept Playwright: {e}", exc_info=True)

    # Start HTTP resume server (if enabled)
    try:
        _start_resume_http_server()
    except Exception as e:
        logger.error(f"Failed to start resume HTTP server: {e}")

    sys.excepthook = _handle_exception"""

content = content.replace(old_activate, new_activate)

with open("sitecustomize.py", "w") as f:
    f.write(content)
print("Done")
