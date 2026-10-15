from src.fieldservice_auth import FieldServiceApp


class Captcha:
    def captcha_verify(self, widget_record_id: str, token: str) -> dict:
        assert widget_record_id == "test-widget"
        assert token == "test-token"
        return {"verified": True}


def test_signup_login_and_follow_up_state_transition():
    app = FieldServiceApp(Captcha())
    session = app.signup("tech@example.com", "pw", "Rin", "test-widget", "test-token")
    order = app.dispatch(session, "WO-7", "12 Main St")
    updated = app.technician_follow_up(session, order.order_id, "photo-1.jpg", "Meter replaced")
    assert updated.dispatch_status == "followed_up"
    assert updated.photos == ["photo-1.jpg"]
    assert app.verify_session(session).name == "Rin"
