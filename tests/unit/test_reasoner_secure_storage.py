from reasoner import ENCRYPTED_PREFIX, _secure_read_text, _secure_write_text


def test_secure_write_and_read_roundtrip(tmp_path):
    fp = tmp_path / "perfil.txt"

    _secure_write_text(str(fp), "dato sensible")

    raw = fp.read_text(encoding="utf-8")
    assert raw.startswith(ENCRYPTED_PREFIX)
    assert "dato sensible" not in raw

    decoded = _secure_read_text(str(fp))
    assert decoded == "dato sensible"


def test_secure_read_plaintext_backward_compatible(tmp_path):
    fp = tmp_path / "legacy.txt"
    fp.write_text("texto plano legado", encoding="utf-8")

    decoded = _secure_read_text(str(fp))
    assert decoded == "texto plano legado"
