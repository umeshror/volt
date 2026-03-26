"""
volt/ota.py — Over-The-Air (OTA) firmware update manager for ESP32.

Coordinates downloading firmware chunks, writing to the inactive A/B partition,
and verifying the boot on next startup to prevent catastrophic failures.
"""

from __future__ import annotations

try:
    from typing import Any, Callable, Dict, Optional
except ImportError:
    pass

try:
    import esp32  # type: ignore
    import urequests as requests  # type: ignore
    from machine import reset  # type: ignore
except ImportError:
    requests = None
    esp32 = None


class OTAManager:
    """
    Manages safe Over-The-Air updates using ESP32 A/B partitions.
    """

    def __init__(self, current_version: str = "1.0.0") -> None:
        self.current_version: str = current_version
        self.chunk_size: int = 4096

    def check_for_update(self, metadata_url: str) -> dict[str, Any] | None:
        """
        Fetch update metadata from the server.
        Expected JSON format: {"version": "1.1.0", "url": "http://.../fw.bin"}
        """
        if requests is None:
            return None  # Host testing environment

        try:
            resp = requests.get(metadata_url)
            if resp.status_code == 200:
                data = resp.json()
                resp.close()
                if isinstance(data, dict) and data.get("version") != self.current_version:
                    return data
            else:
                resp.close()
        except Exception as e:
            print(f"[VOLT/OTA] Metadata fetch failed: {e}")
        return None

    def install_update(self, firmware_url: str, progress_cb: Callable[[int, int], None] | None = None) -> bool:
        """
        Stream down new firmware block-by-block directly into the alternate flash partition.
        """
        if requests is None or esp32 is None:
            return False  # Host testing

        try:
            resp = requests.get(firmware_url, stream=True)
            if resp.status_code != 200:
                print(f"[VOLT/OTA] Firmware download failed: HTTP {resp.status_code}")
                return False

            total_size = int(resp.headers.get("content-length", "0"))

            # Identify the next OTA partition to write into
            partition = esp32.Partition(esp32.Partition.RUNNING).get_next_update()

            print(f"[VOLT/OTA] Starting OTA flash. Size: {total_size} bytes")

            bytes_written: int = 0
            block_num: int = 0

            while True:
                # Some requests implementations read chunks
                chunk = resp.raw.read(self.chunk_size) if hasattr(resp, "raw") else resp.content[bytes_written:bytes_written+self.chunk_size]
                if not chunk:
                    break

                # Write to flash block interface
                # MicroPython blocks are typically 4096 bytes
                partition.writeblocks(block_num, chunk)
                bytes_written += len(chunk)
                block_num += 1

                if progress_cb and total_size > 0:
                    progress_cb(bytes_written, total_size)

            resp.close()

            # Switch boot partition
            partition.set_boot()
            print("[VOLT/OTA] OTA flashing complete. Next boot will use new partition.")
            return True

        except Exception as e:
            print(f"[VOLT/OTA] Flash error: {e}")
            return False

    def commit(self) -> None:
        """
        Call this after a successful boot to permanently accept the new firmware.
        If this isn't called, the ESP32 bootloader may roll back to the previous partition
        on the next reset if rollback protection is enabled in the bootloader.
        """
        if esp32 is None:
            return

        try:
            esp32.Partition.mark_app_valid_cancel_rollback()
            print("[VOLT/OTA] Firmware validated. Rollback cancelled.")
        except AttributeError:
            pass  # Not supported on this specific MicroPython build
        except Exception as e:
            print(f"[VOLT/OTA] Failed to validate firmware: {e}")

    def reboot(self) -> None:
        """Perform a hard reset to boot into the new firmware."""
        try:
            reset()  # type: ignore
        except NameError:
            pass
