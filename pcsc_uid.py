# pcsc_uid.py
import sys
import ctypes
from ctypes import wintypes

# PC/SC Error Codes
SCARD_S_SUCCESS = 0
SCARD_E_NO_SMARTCARD = 0x8010000C
SCARD_W_REMOVED_CARD = 0x80100069
SCARD_W_REMOVED_CARD = 0x80100069


class NoCardDetectedError(Exception):
    pass

# ACR122U系でUID取得（拡張APDU）
GET_UID = bytes.fromhex("FF CA 00 00 00")

def read_uid_hex() -> str:
    if sys.platform.startswith("win"):
        return _read_uid_windows()
    if sys.platform == "darwin":
        return _read_uid_macos()
    raise RuntimeError("This build supports Windows and macOS only.")

def _hex(b: bytes) -> str:
    return b.hex().upper()

def _read_uid_windows() -> str:
    winscard = ctypes.WinDLL("winscard.dll")

    SCARD_SCOPE_USER = 0
    SCARD_S_SUCCESS = 0
    SCARD_SHARE_SHARED = 2
    SCARD_PROTOCOL_T0 = 1
    SCARD_PROTOCOL_T1 = 2
    SCARD_LEAVE_CARD = 0

    hcontext = wintypes.HANDLE()
    rv = winscard.SCardEstablishContext(SCARD_SCOPE_USER, None, None, ctypes.byref(hcontext))
    if rv != SCARD_S_SUCCESS:
        raise RuntimeError(f"SCardEstablishContext failed: 0x{rv:08X}")

    try:
        pcch = wintypes.DWORD(0)
        rv = winscard.SCardListReadersW(hcontext, None, None, ctypes.byref(pcch))
        if rv != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardListReaders(size) failed: 0x{rv:08X}")

        buf = ctypes.create_unicode_buffer(pcch.value)
        rv = winscard.SCardListReadersW(hcontext, None, buf, ctypes.byref(pcch))
        if rv != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardListReaders failed: 0x{rv:08X}")

        readers = [s for s in buf[:].split("\x00") if s]
        if not readers:
            raise RuntimeError("No PC/SC readers found")
        reader = readers[0]

        hcard = wintypes.HANDLE()
        active_proto = wintypes.DWORD()
        rv = winscard.SCardConnectW(
            hcontext, reader, SCARD_SHARE_SHARED,
            SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
            ctypes.byref(hcard), ctypes.byref(active_proto)
        )
        if rv != SCARD_S_SUCCESS:
            # Handle "No Smart Card" errors specifically
            # 0x-7FEFFF97 comes from a signed integer interpretation of 0x80100069 (SCARD_W_REMOVED_CARD)
            # We check for both straightforward hex and signed equivalent just in case, though ctypes usually returns unsigned or raw.
            # However, if ctypes behaves like signed, 0x80100069 might appear as -2146434967 (which is 0x80100069 in 32-bit signed)
            # But the user reported 0x-7FEFFF97 which is -2146435175?
            # Let's perform a proper check.
            # 0x80100069 = SCARD_W_REMOVED_CARD
            # 0x8010000C = SCARD_E_NO_SMARTCARD
            
            # Allow for signed/unsigned mismatch by checking & 0xFFFFFFFF
            rv_unsigned = rv & 0xFFFFFFFF
            if rv_unsigned in (SCARD_W_REMOVED_CARD, SCARD_E_NO_SMARTCARD):
                raise NoCardDetectedError("No smart card present or card removed.")
                
            raise RuntimeError(f"SCardConnect failed: 0x{rv:08X} ({rv})")

        try:
            class SCARD_IO_REQUEST(ctypes.Structure):
                _fields_ = [("dwProtocol", wintypes.DWORD), ("cbPciLength", wintypes.DWORD)]

            pci = SCARD_IO_REQUEST(active_proto.value, ctypes.sizeof(SCARD_IO_REQUEST))
            recv_buf = ctypes.create_string_buffer(258)
            recv_len = wintypes.DWORD(len(recv_buf))

            rv = winscard.SCardTransmit(
                hcard, ctypes.byref(pci),
                GET_UID, len(GET_UID),
                None, recv_buf, ctypes.byref(recv_len)
            )
            if rv != SCARD_S_SUCCESS:
                raise RuntimeError(f"SCardTransmit failed: 0x{rv:08X}")

            resp = recv_buf.raw[:recv_len.value]
            if len(resp) < 2:
                raise RuntimeError("Short response")
            data, sw1, sw2 = resp[:-2], resp[-2], resp[-1]
            if (sw1, sw2) != (0x90, 0x00):
                raise RuntimeError(f"GET_UID failed: SW={sw1:02X}{sw2:02X}")
            return _hex(data)
        finally:
            winscard.SCardDisconnect(hcard, SCARD_LEAVE_CARD)
    finally:
        winscard.SCardReleaseContext(hcontext)


# --- Event-Driven Implementation ---

class SCARD_READERSTATE(ctypes.Structure):
    _fields_ = [
        ("szReader", ctypes.c_wchar_p),
        ("pvUserData", ctypes.c_void_p),
        ("dwCurrentState", wintypes.DWORD),
        ("dwEventState", wintypes.DWORD),
        ("cbAtr", wintypes.DWORD),
        ("rgbAtr", ctypes.c_byte * 36),
    ]

SCARD_STATE_UNAWARE = 0x00000000
SCARD_STATE_IGNORE = 0x00000001
SCARD_STATE_CHANGED = 0x00000002
SCARD_STATE_UNKNOWN = 0x00000004
SCARD_STATE_UNAVAILABLE = 0x00000008
SCARD_STATE_EMPTY = 0x00000010
SCARD_STATE_PRESENT = 0x00000020
SCARD_STATE_ATRMATCH = 0x00000040
SCARD_STATE_EXCLUSIVE = 0x00000080
SCARD_STATE_INUSE = 0x00000100
SCARD_STATE_MUTE = 0x00000200
SCARD_STATE_UNPOWERED = 0x00000400

INFINITE = 0xFFFFFFFF

class NFCReader:
    def __init__(self):
        if not sys.platform.startswith("win"):
            raise RuntimeError("NFCReader class only supports Windows for now.")
            
        self.winscard = ctypes.WinDLL("winscard.dll")
        self.hcontext = wintypes.HANDLE()
        
        rv = self.winscard.SCardEstablishContext(0, None, None, ctypes.byref(self.hcontext))
        if rv != 0:
            raise RuntimeError(f"SCardEstablishContext failed: 0x{rv:08X}")
            
        self.reader_name = None
        self.reader_states = (SCARD_READERSTATE * 1)()
        
    def close(self):
        if self.hcontext:
            self.winscard.SCardReleaseContext(self.hcontext)
            self.hcontext = None

    def _get_readers(self):
        pcch = wintypes.DWORD(0)
        rv = self.winscard.SCardListReadersW(self.hcontext, None, None, ctypes.byref(pcch))
        if rv != 0:
            return []
            
        buf = ctypes.create_unicode_buffer(pcch.value)
        rv = self.winscard.SCardListReadersW(self.hcontext, None, buf, ctypes.byref(pcch))
        if rv != 0:
            return []
            
        return [s for s in buf[:].split("\x00") if s]

    def wait_for_card(self, timeout_ms=1000):
        """
        Wait for a card availability change or presence.
        Returns 'present' if card is there, 'empty' if removed, or None if no reader/timeout.
        This updates internal state to track changes.
        """
        # 1. Find reader if not known
        if not self.reader_name:
            readers = self._get_readers()
            if not readers:
                return None
            self.reader_name = readers[0]
            # Initialize state
            self.reader_states[0].szReader = self.reader_name
            self.reader_states[0].dwCurrentState = SCARD_STATE_UNAWARE

        # 2. Call GetStatusChange
        # We want to wait until the state changes or timeout
        rv = self.winscard.SCardGetStatusChangeW(
            self.hcontext,
            wintypes.DWORD(timeout_ms),
            self.reader_states,
            1
        )
        
        if rv == 0: # Success (State changed or we just checked)
            # Update current state from event state for next call
            event_state = self.reader_states[0].dwEventState
            self.reader_states[0].dwCurrentState = event_state
            
            if event_state & SCARD_STATE_PRESENT:
                return "present"
            if event_state & SCARD_STATE_EMPTY:
                return "empty"
            if event_state & SCARD_STATE_UNAVAILABLE:
                self.reader_name = None # Reader gone, re-scan next time
                return "unavailable"
                
        elif rv == 0x8010000A: # SCARD_E_TIMEOUT
             pass
        else:
            # unexpected error, maybe reader removed
            self.reader_name = None
            
        return None

    def read_uid(self):
        if not self.reader_name:
            return None
            
        hcard = wintypes.HANDLE()
        active_proto = wintypes.DWORD()
        
        rv = self.winscard.SCardConnectW(
            self.hcontext,
            self.reader_name,
            2, # SCARD_SHARE_SHARED
            3, # T0 | T1
            ctypes.byref(hcard),
            ctypes.byref(active_proto)
        )
        
        if rv != 0:
             return None
             
        try:
            # Same APDU logic as before
            class SCARD_IO_REQUEST(ctypes.Structure):
                _fields_ = [("dwProtocol", wintypes.DWORD), ("cbPciLength", wintypes.DWORD)]

            pci = SCARD_IO_REQUEST(active_proto.value, ctypes.sizeof(SCARD_IO_REQUEST))
            recv_buf = ctypes.create_string_buffer(258)
            recv_len = wintypes.DWORD(len(recv_buf))
            
            rv = self.winscard.SCardTransmit(
                hcard, ctypes.byref(pci),
                GET_UID, len(GET_UID),
                None, recv_buf, ctypes.byref(recv_len)
            )
            
            if rv == 0:
                resp = recv_buf.raw[:recv_len.value]
                if len(resp) >= 2 and resp[-2:] == b'\x90\x00':
                    return _hex(resp[:-2])
        finally:
            self.winscard.SCardDisconnect(hcard, 0) # SCARD_LEAVE_CARD
            
        return None

def _read_uid_macos() -> str:
    pcsc = ctypes.CDLL("/System/Library/Frameworks/PCSC.framework/PCSC")

    SCARD_SCOPE_USER = 0
    SCARD_S_SUCCESS = 0
    SCARD_SHARE_SHARED = 2
    SCARD_PROTOCOL_T0 = 1
    SCARD_PROTOCOL_T1 = 2
    SCARD_LEAVE_CARD = 0

    SCARDCONTEXT = ctypes.c_ulong
    SCARDHANDLE = ctypes.c_ulong
    DWORD = ctypes.c_uint32

    hcontext = SCARDCONTEXT()
    rv = pcsc.SCardEstablishContext(SCARD_SCOPE_USER, None, None, ctypes.byref(hcontext))
    if rv != SCARD_S_SUCCESS:
        raise RuntimeError(f"SCardEstablishContext failed: 0x{rv:08X}")

    try:
        pcch = DWORD(0)
        rv = pcsc.SCardListReaders(hcontext, None, None, ctypes.byref(pcch))
        if rv != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardListReaders(size) failed: 0x{rv:08X}")

        buf = ctypes.create_string_buffer(pcch.value)
        rv = pcsc.SCardListReaders(hcontext, None, buf, ctypes.byref(pcch))
        if rv != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardListReaders failed: 0x{rv:08X}")

        readers = [s.decode("utf-8") for s in buf.raw.split(b"\x00") if s]
        if not readers:
            raise RuntimeError("No PC/SC readers found")
        reader = readers[0].encode("utf-8")

        hcard = SCARDHANDLE()
        active_proto = DWORD()
        rv = pcsc.SCardConnect(
            hcontext, reader, SCARD_SHARE_SHARED,
            SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
            ctypes.byref(hcard), ctypes.byref(active_proto)
        )
        if rv != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardConnect failed: 0x{rv:08X}")

        try:
            class SCARD_IO_REQUEST(ctypes.Structure):
                _fields_ = [("dwProtocol", DWORD), ("cbPciLength", DWORD)]

            pci = SCARD_IO_REQUEST(active_proto.value, ctypes.sizeof(SCARD_IO_REQUEST))
            recv_buf = ctypes.create_string_buffer(258)
            recv_len = DWORD(len(recv_buf))

            rv = pcsc.SCardTransmit(
                hcard, ctypes.byref(pci),
                GET_UID, len(GET_UID),
                None, recv_buf, ctypes.byref(recv_len)
            )
            if rv != SCARD_S_SUCCESS:
                raise RuntimeError(f"SCardTransmit failed: 0x{rv:08X}")

            resp = recv_buf.raw[:recv_len.value]
            if len(resp) < 2:
                raise RuntimeError("Short response")
            data, sw1, sw2 = resp[:-2], resp[-2], resp[-1]
            if (sw1, sw2) != (0x90, 0x00):
                raise RuntimeError(f"GET_UID failed: SW={sw1:02X}{sw2:02X}")
            return _hex(data)
        finally:
            pcsc.SCardDisconnect(hcard, SCARD_LEAVE_CARD)
    finally:
        pcsc.SCardReleaseContext(hcontext)



