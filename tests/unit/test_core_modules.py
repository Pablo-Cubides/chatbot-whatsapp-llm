import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_chat_sessions_import():
    """Test chat_sessions module can be imported"""
    import chat_sessions
    assert chat_sessions is not None


def test_reasoner_import():
    """Test reasoner module can be imported"""
    import reasoner
    assert reasoner is not None


def test_whatsapp_automator_import():
    """Test whatsapp_automator module can be imported"""
    import whatsapp_automator
    assert whatsapp_automator is not None


def test_admin_panel_import():
    """Test admin_panel module can be imported"""
    import admin_panel
    assert admin_panel is not None
