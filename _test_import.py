import sys, traceback
sys.path.insert(0, '.')
try:
    from core.app_logging import configurar_logging_basico, log_event
    configurar_logging_basico()
    import main_medicare
    print('OK')
except Exception as e:
    traceback.print_exc()
