import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

usb_cdc = ModuleType("usb_cdc")
setattr(usb_cdc, "data", None)
sys.modules.setdefault("usb_cdc", usb_cdc)
