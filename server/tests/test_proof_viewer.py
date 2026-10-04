"""Фото наказания открыто тому, кто видит карточку, а не только сотруднику панели."""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from admin_auth import may_see_proof
from admin_routes import photo_proxy


def test_a_group_seat_opens_the_proof_without_a_staff_account():
    assert may_see_proof(has_seat=True) is True
    assert may_see_proof(account_active=True) is True
    assert may_see_proof(creator=True) is True
    assert may_see_proof(owner=True) is True
    assert may_see_proof() is False


def test_photo_proxy_uses_the_proof_viewer():
    default = inspect.signature(photo_proxy).parameters["_admin_id"].default
    assert getattr(default, "dependency", None) is not None
    assert default.dependency.__name__ == "require_proof_viewer"
