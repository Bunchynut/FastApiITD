from src.serves.auth import auth


def test_create_access_token():
    data = {'user_id': 1}
    jwt_token = auth().create_access_token(data)

    assert jwt_token

    payload = auth().decode_token(jwt_token)
    assert payload
    assert payload['user_id'] == data['user_id']
