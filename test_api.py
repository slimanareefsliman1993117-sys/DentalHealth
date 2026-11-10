"""Run isolated API regression tests; never connect to or clean a live database."""
if __name__ == '__main__':
    import subprocess,sys
    from pathlib import Path
    raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).parent/'validation/run.py'), 'test', 'accounts', 'validation.test_admin', 'validation.test_readiness', '--verbosity', '2']))
