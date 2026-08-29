import os
import requests
import threading

class SheetSyncManager:
    def __init__(self, apps_script_url=None):
        self.url = apps_script_url or os.environ.get(
            "APPS_SCRIPT_URL", 
            "https://script.google.com/macros/s/1em3b8VyMb-Ty_-adbPNDwR7H1fdohXpKSuTeZ1/exec"
        )
        self.enabled = bool(self.url) and "REPLACE_WITH" not in self.url

    def _send_payload(self, payload):
        if not self.enabled:
            return
        try:
            requests.post(self.url, json=payload, timeout=5)
        except Exception as e:
            print(f"[SheetSync Warning] Failed to push trade to Google Sheets: {e}")

    def push_trade_async(self, trade_record):
        if not self.enabled:
            return
        thread = threading.Thread(target=self._send_payload, args=(trade_record,))
        thread.daemon = True
        thread.start()
