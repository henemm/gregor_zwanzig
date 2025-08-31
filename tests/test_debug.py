from app.debug import DebugBuffer

def test_debug_buffer_roundtrip():
    dbg = DebugBuffer()
    dbg.add("line1")
    dbg.add("line2")
    assert "line1" in dbg.as_text()
    assert dbg.as_text() == dbg.email_subset()