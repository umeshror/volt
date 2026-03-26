import pytest
from unittest.mock import MagicMock
from volt import ota

def test_check_for_update_newer():
    mgr = ota.OTAManager("1.0.0")
    
    # Mock requests module
    mock_requests = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "1.1.0", "url": "http://fw"}
    mock_requests.get.return_value = mock_resp
    
    # Inject mock
    ota.requests = mock_requests
    
    res = mgr.check_for_update("http://fw-url")
    
    assert res is not None
    assert res["version"] == "1.1.0"
    mock_resp.close.assert_called_once()

def test_check_for_update_same_version():
    mgr = ota.OTAManager("1.0.0")
    mock_requests = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"version": "1.0.0", "url": "http://fw"}
    mock_requests.get.return_value = mock_resp
    ota.requests = mock_requests
    
    assert mgr.check_for_update("http://fw-url") is None

def test_install_update():
    mgr = ota.OTAManager("1.0.0")
    
    # Mock requests
    mock_requests = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "8192"}
    mock_resp.raw.read.side_effect = [b"A" * 4096, b"B" * 4096, b""]
    mock_requests.get.return_value = mock_resp
    ota.requests = mock_requests
    
    # Mock esp32
    mock_esp32 = MagicMock()
    mock_partition = MagicMock()
    mock_esp32.Partition.RUNNING = 1
    mock_esp32.Partition.return_value.get_next_update.return_value = mock_partition
    ota.esp32 = mock_esp32
    
    progress_calls = []
    def progress(written, total):
        progress_calls.append((written, total))
        
    res = mgr.install_update("http://fw", progress)
    
    assert res is True
    assert mock_partition.writeblocks.call_count == 2
    mock_partition.set_boot.assert_called_once()
    assert progress_calls == [(4096, 8192), (8192, 8192)]

def test_commit():
    mgr = ota.OTAManager("1.0.0")
    mock_esp32 = MagicMock()
    ota.esp32 = mock_esp32
    
    mgr.commit()
    
    mock_esp32.Partition.mark_app_valid_cancel_rollback.assert_called_once()
