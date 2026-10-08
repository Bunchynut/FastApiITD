import pytest
from pydantic import ValidationError

from src.Schemas.Schemas import HotelPatch
from src.Schemas.rooms import PutRoomsPutSchema, RoomsPatchSchema
from src.Schemas.users import (
    UserAdd,
    UserId,
    UserId_With_Hashed,
    UserLogin,
    UserRegister,
)
from src.model.users import SexEnum, UsersOrm


@pytest.fixture
def user_data():
    return {
        "email": "person@example.com",
        "password": "password",
        "number": "+79999999999",
        "first_name": "Anna",
        "second_name": "Ivanova",
        "sex": "female",
    }


@pytest.mark.parametrize("sex", ["male", "female"])
def test_registration_normalizes_email_and_parses_sex(user_data, sex):
    user = UserRegister.model_validate(
        {**user_data, "email": "person@EXAMPLE.COM", "sex": sex}
    )
    assert user.email == "person@example.com"
    assert user.sex is SexEnum(sex)
    assert user.number == "+79999999999"


@pytest.mark.parametrize("schema", [UserRegister, UserLogin])
@pytest.mark.parametrize("email", ["", "not-an-email", "person@", "@example.com"])
def test_user_request_rejects_invalid_email(user_data, schema, email):
    with pytest.raises(ValidationError) as error:
        schema.model_validate({**user_data, "email": email})
    assert error.value.errors()[0]["loc"] == ("email",)


@pytest.mark.parametrize("sex", ["unknown", "", None])
def test_registration_rejects_invalid_sex(user_data, sex):
    with pytest.raises(ValidationError) as error:
        UserRegister.model_validate({**user_data, "sex": sex})
    assert error.value.errors()[0]["loc"] == ("sex",)


@pytest.mark.parametrize(
    "field", ["email", "password", "number", "first_name", "second_name", "sex"]
)
def test_registration_requires_user_fields(user_data, field):
    del user_data[field]
    with pytest.raises(ValidationError) as error:
        UserRegister.model_validate(user_data)
    assert error.value.errors()[0]["loc"] == (field,)
    assert error.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize(
    "number", ["1234567890", "+1234567890", "123456789012345", "+123456789012345"]
)
def test_persisted_user_accepts_phone_length_boundaries(user_data, number):
    data = {key: value for key, value in user_data.items() if key != "password"}
    user = UserAdd.model_validate(
        {**data, "hashed_password": "stored-hash", "number": number}
    )
    assert user.number == number


@pytest.mark.parametrize(
    "number", ["123456789", "+1234567890123456", "7999abc9999", "+7 999 999 9999", ""]
)
def test_persisted_user_rejects_invalid_phone(user_data, number):
    data = {key: value for key, value in user_data.items() if key != "password"}
    with pytest.raises(ValidationError) as error:
        UserAdd.model_validate(
            {**data, "hashed_password": "stored-hash", "number": number}
        )
    assert error.value.errors()[0]["loc"] == ("number",)


@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="UserRegister does not apply the phone validation required by UserAdd",
)
def test_registration_rejects_invalid_phone_at_request_boundary(user_data):
    with pytest.raises(ValidationError):
        UserRegister.model_validate({**user_data, "number": "invalid-phone"})


def test_public_user_maps_orm_without_exposing_password():
    orm_user = UsersOrm(
        id=17,
        email="person@example.com",
        number="+79999999999",
        first_name="Anna",
        second_name="Ivanova",
        sex=SexEnum.female,
        hashed_password="stored-hash",
    )
    public = UserId.model_validate(orm_user).model_dump(mode="json")
    assert public == {
        "id": 17,
        "email": "person@example.com",
        "number": "+79999999999",
        "first_name": "Anna",
        "second_name": "Ivanova",
        "sex": "female",
    }
    private = UserId_With_Hashed.model_validate(orm_user)
    assert private.hashed_password == "stored-hash"


@pytest.mark.parametrize(
    "schema, data",
    [(HotelPatch, {"location": "Paris"}), (RoomsPatchSchema, {"price": 2500})],
)
def test_partial_update_excludes_fields_not_supplied(schema, data):
    assert schema.model_validate(data).model_dump(exclude_unset=True) == data


def test_partial_update_keeps_explicit_null():
    assert RoomsPatchSchema(description=None).model_dump(exclude_unset=True) == {
        "description": None
    }


def test_room_update_facility_defaults_are_independent():
    data = {"title": "Suite", "description": "Sea view", "price": 2500, "quantity": 2}
    first = PutRoomsPutSchema.model_validate(data)
    second = PutRoomsPutSchema.model_validate(data)
    first.facilities_ids.append(1)
    assert second.facilities_ids == []
