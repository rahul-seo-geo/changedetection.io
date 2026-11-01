import sys
import pytest
from dealhound import cli


def test_cli_help(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['dealhound.cli', '--help'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
