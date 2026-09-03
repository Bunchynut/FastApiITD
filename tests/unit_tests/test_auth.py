from src.serves.auth import auth


def test_create_access_token():
    data = {'user_id': 1}
    jwt_token = auth().create_access_token(data)

    assert jwt_token
    assert isinstance(jwt_token, str)